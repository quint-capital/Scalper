"""Quint Capital V3.11 research backtester: M15/M5/M1, tick exits, excursion and OOS diagnostics.
Analysis-only: no broker orders are sent. This is a diagnostic simulation, not a profit guarantee.
"""
import argparse, asyncio, csv, json, math, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
import websockets
from engine import analyze

DEFAULT_SYMBOL = os.getenv("DERIV_SYMBOL", "R_75")
WS_URL = os.getenv("DERIV_WS_URL", "wss://ws.binaryws.com/websockets/v3")
OUT_DIR = Path(os.getenv("BACKTEST_OUTPUT_DIR", "backtest_results"))
BATCH = min(5000, max(100, int(os.getenv("TICK_BATCH_SIZE", "5000"))))
TF_SECONDS = {"M1":60, "M5":300, "M15":900}

async def request_history(ws, payload, timeout=30):
    await ws.send(json.dumps(payload))
    end = time.monotonic() + timeout
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0: raise TimeoutError("Timed out waiting for historical ticks")
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
        if msg.get("error"):
            err = msg["error"]
            raise RuntimeError(f"Deriv API error {err.get('code','')}: {err.get('message','unknown error')}")
        if msg.get("msg_type") == "history" or "history" in msg: return msg

async def download_ticks(symbol, days):
    end_epoch = int(time.time())
    start_epoch = end_epoch - int(days * 86400)
    collected = {}
    cursor = end_epoch
    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20, close_timeout=10, open_timeout=20) as ws:
        batch_num = 0
        while cursor > start_epoch:
            res = await request_history(ws, {"ticks_history":symbol,"end":cursor,"count":BATCH,"style":"ticks"})
            hist = res.get("history") or {}
            times, prices = hist.get("times") or [], hist.get("prices") or []
            if not times or not prices: break
            batch_num += 1
            old_count = len(collected)
            for ts, price in zip(times, prices):
                ts = int(ts)
                if start_epoch <= ts <= end_epoch:
                    # One-second timestamps can contain multiple quotes. Preserve response order per batch.
                    key = (ts, batch_num, len(collected))
                    collected[key] = float(price)
            earliest = min(map(int, times))
            print(f"[DOWNLOAD] batch={batch_num} returned={len(times)} earliest={earliest} ticks_in_window={len(collected)}", flush=True)
            if earliest <= start_epoch: break
            if earliest >= cursor or len(collected) == old_count:
                raise RuntimeError("History pagination stopped advancing; refusing to report an incomplete backtest.")
            cursor = earliest - 1
            await asyncio.sleep(0.05)
            if batch_num > 20000: raise RuntimeError("Safety stop: excessive history batches")
    ticks = sorted(((k[0], k[1], k[2], p) for k,p in collected.items()), key=lambda x:(x[0],x[1],x[2]))
    # Remove exact adjacent duplicates while preserving different prices at the same epoch.
    clean=[]; prev=None
    for ts,batch,seq,p in ticks:
        item=(ts,p)
        if item != prev: clean.append((ts,p))
        prev=item
    if len(clean) < 1000: raise RuntimeError(f"Only {len(clean)} ticks downloaded; cannot make a meaningful seven-day replay.")
    return start_epoch,end_epoch,clean

def candles_from_ticks(ticks, seconds):
    bars={}
    for ts,p in ticks:
        bucket=ts-(ts%seconds)
        if bucket not in bars: bars[bucket]=[p,p,p,p,1]
        else:
            b=bars[bucket]; b[1]=max(b[1],p); b[2]=min(b[2],p); b[3]=p; b[4]+=1
    return [{"ts":ts,"open":b[0],"high":b[1],"low":b[2],"close":b[3],"volume":b[4]} for ts,b in sorted(bars.items())]

def write_tick_csv(path,ticks):
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['epoch','utc','price'])
        for ts,p in ticks: w.writerow([ts,datetime.fromtimestamp(ts,timezone.utc).isoformat(),f'{p:.8f}'])

def replay(ticks, candles, warmup=300):
    m1=candles['M1']; times=[t[0] for t in ticks]
    trades=[]; active=None; tick_cursor=0; cooldown_until=-1; last_bar_signal=None
    # Iterate only at completed M1 closes. M15/M5/M1 inputs contain completed candles only.
    for i,bar in enumerate(m1):
        decision=bar['ts']+60
        if i < warmup: continue
        if active:
            while tick_cursor < len(ticks) and ticks[tick_cursor][0] < active['entry_ts']: tick_cursor += 1
            while tick_cursor < len(ticks) and ticks[tick_cursor][0] < decision:
                ts,price=ticks[tick_cursor]
                # Track favorable/adverse excursions before checking exit on this tick.
                if active['direction']=='BUY':
                    favorable=max(0.0, price-active['entry'])/active['risk_points']
                    adverse=max(0.0, active['entry']-price)/active['risk_points']
                    hit_sl = price <= active['sl']; hit_tp = price >= active['tp1']
                else:
                    favorable=max(0.0, active['entry']-price)/active['risk_points']
                    adverse=max(0.0, price-active['entry'])/active['risk_points']
                    hit_sl = price >= active['sl']; hit_tp = price <= active['tp1']
                active['MFE_R'] = max(active.get('MFE_R', 0.0), favorable)
                active['MAE_R'] = max(active.get('MAE_R', 0.0), adverse)
                if hit_sl:
                    active.update(exit_ts=ts,exit_price=price,outcome='SL',realized_R=-1.0,
                                  bars_held=max(1, i-active['entry_bar_index']))
                    trades.append(active); active=None; cooldown_until=i+3; tick_cursor+=1; break
                if hit_tp:
                    active.update(exit_ts=ts,exit_price=price,outcome='TP1',realized_R=active['planned_RR'],
                                  bars_held=max(1, i-active['entry_bar_index']))
                    trades.append(active); active=None; tick_cursor+=1; break
                tick_cursor+=1
            if active: continue
        if i < cooldown_until: continue
        frames={}
        for tf,sec in TF_SECONDS.items():
            # Only bars whose close time is at/before decision time are eligible.
            eligible=[]
            for c in candles[tf]:
                if c['ts']+sec <= decision: eligible.append(c)
                else: break
            frames[tf]=eligible[-3000:]
        try: result=analyze(frames)
        except Exception as exc:
            print(f'[WARN] engine error at {decision}: {type(exc).__name__}: {exc}',flush=True); continue
        state=result.get('state'); setup=result.get('setup') or {}
        if state not in ('BUY SETUP','SELL SETUP') or not setup:
            last_bar_signal=None; continue
        direction='BUY' if result.get('direction')=='BULLISH' else 'SELL' if result.get('direction')=='BEARISH' else None
        if not direction: continue
        try: entry=float(setup['entry']); sl=float(setup['sl']); tp=float(setup['tp1'])
        except (KeyError,TypeError,ValueError): continue
        risk=(entry-sl) if direction=='BUY' else (sl-entry)
        reward=(tp-entry) if direction=='BUY' else (entry-tp)
        if not all(map(math.isfinite,(entry,sl,tp,risk,reward))) or risk<=0 or reward<=0: continue
        if (direction=='BUY' and not sl < entry < tp) or (direction=='SELL' and not tp < entry < sl): continue
        # Prevent repeated entry on the same completed M1 candle.
        if last_bar_signal == bar['ts']: continue
        last_bar_signal=bar['ts']
        active={"trade_id":len(trades)+1,"entry_ts":decision,"entry_utc":datetime.fromtimestamp(decision,timezone.utc).isoformat(),
          "entry_bar_epoch":bar['ts'],"entry_bar_index":i,"direction":direction,"entry":entry,"sl":sl,"tp1":tp,"risk_points":risk,
          "planned_RR":reward/risk,"setup_type":result.get('setup_type',''),"structure_score":result.get('structure_score'),
          "trigger_score":result.get('trigger_score'),"market_regime":(result.get('market_regime') or {}).get('label',''),
          "source_direction":(setup.get('source_direction') or result.get('original_direction','')),
          "emitted_direction":(setup.get('emitted_direction') or direction),
          "M1_volatility":(result.get('readings') or {}).get('M1',{}).get('volatility','UNKNOWN'),
          "M5_volatility":(result.get('readings') or {}).get('M5',{}).get('volatility','UNKNOWN'),
          "M15_volatility":(result.get('readings') or {}).get('M15',{}).get('volatility','UNKNOWN'),
          "MFE_R":0.0,"MAE_R":0.0}
        # Do not use future ticks to decide whether to enter. The next loop resolves exits from the entry timestamp onward.
    return trades,active

def _metrics(trades, cost_r=0.0):
    wins=[t for t in trades if t['realized_R']-cost_r>0]
    losses=[t for t in trades if t['realized_R']-cost_r<0]
    net=sum(t['realized_R']-cost_r for t in trades)
    gp=sum(t['realized_R']-cost_r for t in wins)
    gl=abs(sum(t['realized_R']-cost_r for t in losses))
    equity=peak=dd=0.0
    for t in trades:
        equity += t['realized_R']-cost_r
        peak=max(peak,equity); dd=max(dd,peak-equity)
    return {"trades":len(trades), "wins":len(wins), "losses":len(losses),
      "win_rate_pct":round(100*len(wins)/len(trades),2) if trades else 0.0,
      "net_R_after_cost":round(net,4), "profit_factor_after_cost":round(gp/gl,4) if gl else ("infinite" if gp else 0.0),
      "average_R_per_trade_after_cost":round(net/len(trades),4) if trades else 0.0,
      "max_drawdown_R_after_cost":round(dd,4), "gross_profit_R_after_cost":round(gp,4),
      "gross_loss_R_after_cost":round(gl,4),
      "mean_MFE_R":round(sum(t.get('MFE_R',0) for t in trades)/len(trades),4) if trades else 0.0,
      "mean_MAE_R":round(sum(t.get('MAE_R',0) for t in trades)/len(trades),4) if trades else 0.0}

def summary_for(trades,unresolved,cost_r=0.0):
    # Chronological split: earliest 70% is diagnostic development sample, latest 30% is holdout.
    split=int(len(trades)*0.70)
    train=trades[:split]; test=trades[split:]
    by_regime={}
    for t in trades:
        key=t.get('market_regime') or 'UNKNOWN'
        by_regime.setdefault(key,[]).append(t)
    by_volatility={}
    for t in trades:
        key=t.get('M5_volatility') or 'UNKNOWN'
        by_volatility.setdefault(key,[]).append(t)
    return {"resolved_trades":len(trades),"unresolved_open_trade":bool(unresolved),
      "gross_results_before_cost":_metrics(trades,0.0),
      "net_results_at_configured_cost":_metrics(trades,cost_r),
      "assumed_round_trip_cost_R":cost_r,
      "chronological_70_30_split":{"development_sample":_metrics(train,cost_r),"holdout_sample_latest_30pct":_metrics(test,cost_r),
        "warning":"A small holdout with few trades is inconclusive; this is a chronological diagnostic split, not parameter optimization."},
      "results_by_market_regime":{k:_metrics(v,cost_r) for k,v in by_regime.items()},
      "results_by_M5_volatility":{k:_metrics(v,cost_r) for k,v in by_volatility.items()},
      "note":"MFE/MAE are measured from the assumed entry price. Cost is a user-supplied sensitivity assumption in R per completed trade, not a verified Deriv fee/slippage quote. Unresolved trades are excluded from realized metrics."}

async def main():
    parser=argparse.ArgumentParser(description='Deriv tick-level paper backtest for Quint Capital V75 V3.11 M15/M5/M1 research build')
    parser.add_argument('--days',type=int,default=int(os.getenv('BACKTEST_DAYS','7')))
    parser.add_argument('--symbol',default=DEFAULT_SYMBOL)
    parser.add_argument('--cost-r',type=float,default=float(os.getenv('BACKTEST_COST_R','0.03')), help='assumed round-trip cost in R per resolved trade; sensitivity assumption, default 0.03R')
    args=parser.parse_args()
    if args.days<1 or args.days>30: parser.error('--days must be between 1 and 30')
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    print(f'[START] Downloading {args.days} days of {args.symbol} tick history. No orders will be placed.',flush=True)
    start,end,ticks=await download_ticks(args.symbol,args.days)
    tick_path=OUT_DIR/f'{args.symbol}_{args.days}d_ticks.csv'; write_tick_csv(tick_path,ticks)
    candles={tf:candles_from_ticks(ticks,sec) for tf,sec in TF_SECONDS.items()}
    print('[REPLAY] Running V3.11 engine on completed M15/M5/M1 candles; recording MFE/MAE and holdout diagnostics...',flush=True)
    trades,unresolved=replay(ticks,candles)
    report=summary_for(trades,unresolved,args.cost_r)
    report.update({"symbol":args.symbol,"days_requested":args.days,"ticks_downloaded":len(ticks),
      "start_utc":datetime.fromtimestamp(start,timezone.utc).isoformat(),"end_utc":datetime.fromtimestamp(end,timezone.utc).isoformat(),
      "strategy_engine":"Included reversed M15/M5/M1 engine.py; V3.11 research diagnostics","data_source":"Deriv ticks_history API","mode":"historical paper simulation; no broker execution"})
    summary_path=OUT_DIR/f'{args.symbol}_{args.days}d_summary.json'; summary_path.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    trade_path=OUT_DIR/f'{args.symbol}_{args.days}d_trades.csv'
    fields=sorted(set().union(*(x.keys() for x in trades))) if trades else ['trade_id']
    with open(trade_path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(trades)
    print('\n=== BACKTEST SUMMARY ===')
    for k,v in report.items(): print(f'{k}: {v}')
    print(f'\nRaw ticks: {tick_path}\nTrades: {trade_path}\nSummary: {summary_path}',flush=True)
    print('CAUTION: seven days is a short sample. The 70/30 split is only a diagnostic; validate timing, costs, and unresolved trades before judging profitability.',flush=True)

if __name__=='__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print('Stopped by user.'); sys.exit(130)
    except Exception as exc: print(f'[FATAL] {type(exc).__name__}: {exc}',file=sys.stderr); sys.exit(1)
