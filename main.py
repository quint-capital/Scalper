#!/usr/bin/env python3
"""Quint Capital V75 Research Engine v1.2 — single-file, 7-day default, analysis only."""
#!/usr/bin/env python3
"""Quint Capital V75 research backtester. Analysis only; never places trades."""
import asyncio, csv, json, math, os, statistics, time
from contextlib import asynccontextmanager
from pathlib import Path
import websockets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

def _ensure_app_id(url, fallback_app_id=None):
    """Ensure a configured Deriv WebSocket URL includes an app_id query parameter."""
    if not url:
        return url
    parts = urlsplit(url.strip())
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if not query.get('app_id'):
        query['app_id'] = fallback_app_id or os.getenv('DERIV_APP_ID', '1089')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

DEFAULT_WS_URLS = [
    _ensure_app_id(os.getenv('DERIV_WS_URL', 'wss://ws.derivws.com/websockets/v3?app_id=1089')),
    _ensure_app_id('wss://frontend.binaryws.com/websockets/v3?l=EN&app_id=1089'),
]
@asynccontextmanager
async def connect_deriv():
    errors = []
    seen = set()
    ws = None
    for url in DEFAULT_WS_URLS:
        if not url or url in seen: continue
        seen.add(url)
        try:
            print(f'[CONNECTION] Trying Deriv endpoint: {url.split("?")[0]}', flush=True)
            ws = await websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=10, max_size=8_000_000)
            print(f'[CONNECTION] Connected via {url.split("?")[0]}', flush=True)
            break
        except Exception as exc:
            errors.append(f'{url.split("?")[0]} => {type(exc).__name__}: {exc}')
            print(f'[CONNECTION][WARNING] Endpoint failed: {type(exc).__name__}: {exc}', flush=True)
    if ws is None:
        raise ConnectionError('All Deriv WebSocket endpoints failed. ' + ' | '.join(errors))
    try:
        yield ws
    finally:
        await ws.close()

SYMBOL_REQUEST = os.getenv('DERIV_SYMBOL', 'R_75')
DATA_DIR = Path(os.getenv('DATA_DIR', '/app/data'))
OUT_DIR = Path(os.getenv('BACKTEST_OUTPUT_DIR', str(DATA_DIR / 'backtests')))

async def request(ws, payload, rid):
    payload = dict(payload); payload['req_id'] = rid
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get('req_id') != rid:
            continue
        if msg.get('error'):
            raise RuntimeError(msg['error'].get('message', str(msg['error'])))
        return msg

async def fetch_history(days=30):
    now = int(time.time())
    start = now - int(days) * 86400
    rows_by_ts = {}
    async with connect_deriv() as ws:
        sym_msg = await request(ws, {'active_symbols':'brief','product_type':'basic'}, 1)
        symbols = sym_msg.get('active_symbols', [])
        symbol = next((s.get('symbol') for s in symbols if s.get('symbol','').upper() == SYMBOL_REQUEST.upper()), None)
        if not symbol:
            candidates = [s for s in symbols if 'volatility 75' in (s.get('display_name') or s.get('name') or '').lower()]
            symbol = next((s.get('symbol') for s in candidates if s.get('symbol') == 'R_75'), None) or (candidates[0].get('symbol') if candidates else None)
        if not symbol:
            sample = ', '.join(s.get('symbol','') for s in symbols[:20])
            raise RuntimeError(f'Could not resolve Volatility 75 symbol. First returned symbols: {sample}')
        print(f'[DATA] Resolved Deriv symbol: {symbol}', flush=True)
        cursor = start
        rid = 10
        chunk_seconds = 60 * 60 * 24 * 3
        while cursor < now:
            end = min(cursor + chunk_seconds, now)
            msg = await request(ws, {'ticks_history':symbol,'start':cursor,'end':end,'style':'candles','granularity':60,'subscribe':0}, rid)
            rid += 1
            candles = msg.get('candles') or []
            for c in candles:
                try:
                    ts = int(c['epoch'])
                    row = {'ts':ts,'open':float(c['open']),'high':float(c['high']),'low':float(c['low']),'close':float(c['close'])}
                    if all(math.isfinite(row[k]) for k in ('open','high','low','close')) and row['high'] >= max(row['open'],row['close']) and row['low'] <= min(row['open'],row['close']):
                        rows_by_ts[ts] = row
                except (KeyError, TypeError, ValueError):
                    continue
            print(f'[DATA] Fetch chunk {time.strftime("%Y-%m-%d", time.gmtime(cursor))} -> {time.strftime("%Y-%m-%d", time.gmtime(end))}: {len(candles)} candles returned; {len(rows_by_ts)} unique', flush=True)
            cursor = end + 1
            await asyncio.sleep(0.15)
    return symbol, [rows_by_ts[k] for k in sorted(rows_by_ts) if k < now - (now % 60)]

def aggregate(candles, minutes):
    step = minutes * 60; out = {}
    for c in candles:
        k = (c['ts'] // step) * step
        if k not in out:
            out[k] = {'ts':k,'open':c['open'],'high':c['high'],'low':c['low'],'close':c['close']}
        else:
            out[k]['high'] = max(out[k]['high'], c['high'])
            out[k]['low'] = min(out[k]['low'], c['low'])
            out[k]['close'] = c['close']
    return [out[k] for k in sorted(out)]

def ema(values, period):
    if len(values) < period: return None
    a = 2 / (period + 1); x = sum(values[:period]) / period
    for v in values[period:]: x = a * v + (1-a) * x
    return x

def atr(candles, period=14):
    if len(candles) < period + 1: return None
    tr=[]
    for i in range(1,len(candles)):
        c,p=candles[i],candles[i-1]
        tr.append(max(c['high']-c['low'],abs(c['high']-p['close']),abs(c['low']-p['close'])))
    return sum(tr[-period:]) / period if tr else None

def trend(candles):
    closes=[c['close'] for c in candles]
    e8,e21=ema(closes,8),ema(closes,21)
    if e8 is None or e21 is None:return 0
    if e8 > e21 and closes[-1] > e8:return 1
    if e8 < e21 and closes[-1] < e8:return -1
    return 0

def make_signals(m1, m5, m15, i):
    """Signal uses only fully closed bars through i; entry is next M1 open."""
    if i < 80:return []
    # Bound indicator history so the 30-day walk-forward stays linear-time in practice.
    hist=m1[max(0, i-300):i+1]
    cur=hist[-1]; prev=hist[-2]
    t5=trend(m5); t15=trend(m15)
    a=atr(hist,14)
    if not a or a <= 0:return []
    closes=[x['close'] for x in hist]
    e8,e20=ema(closes,8),ema(closes,20)
    prev20=hist[-21:-1]
    if len(prev20)<20:return []
    prior_high=max(x['high'] for x in prev20); prior_low=min(x['low'] for x in prev20)
    signals=[]
    # 1) Momentum breakout continuation: closed close breaks prior 20-bar extreme with HTF alignment.
    if cur['close'] > prior_high and t5==1 and t15==1: signals.append(('MOMENTUM_BREAKOUT','BUY',a))
    if cur['close'] < prior_low and t5==-1 and t15==-1: signals.append(('MOMENTUM_BREAKOUT','SELL',a))
    # 2) Trend pullback: HTF aligned; price tags/approaches EMA20 then closes back through EMA8.
    if t5==1 and t15==1 and cur['low'] <= (e20 or cur['close']) and cur['close'] > (e8 or cur['close']) and cur['close'] > prev['close']:
        signals.append(('TREND_PULLBACK','BUY',a))
    if t5==-1 and t15==-1 and cur['high'] >= (e20 or cur['close']) and cur['close'] < (e8 or cur['close']) and cur['close'] < prev['close']:
        signals.append(('TREND_PULLBACK','SELL',a))
    # 3) Failed break: wick sweeps prior range and close returns inside.
    if cur['low'] < prior_low and cur['close'] > prior_low and cur['close'] > cur['open']:
        signals.append(('FAILED_BREAK_REVERSAL','BUY',a))
    if cur['high'] > prior_high and cur['close'] < prior_high and cur['close'] < cur['open']:
        signals.append(('FAILED_BREAK_REVERSAL','SELL',a))
    # 4) Range rejection: no strong M5 trend, wick at range edge, close returns within.
    if t5==0 and cur['low'] <= min(x['low'] for x in prev20) and cur['close'] > cur['open'] and cur['close'] > prior_low:
        signals.append(('RANGE_REJECTION','BUY',a))
    if t5==0 and cur['high'] >= max(x['high'] for x in prev20) and cur['close'] < cur['open'] and cur['close'] < prior_high:
        signals.append(('RANGE_REJECTION','SELL',a))
    # 5) Compression expansion: recent 5-bar average range compressed vs prior 20; current candle expands and breaks local edge.
    recent=hist[-5:]; baseline=hist[-25:-5]
    if len(baseline)==20:
        r_recent=sum(x['high']-x['low'] for x in recent[:-1])/4
        r_base=sum(x['high']-x['low'] for x in baseline)/20
        if r_base>0 and r_recent < 0.7*r_base:
            if cur['close'] > max(x['high'] for x in hist[-6:-1]) and cur['close'] > cur['open']:
                signals.append(('COMPRESSION_EXPANSION','BUY',a))
            if cur['close'] < min(x['low'] for x in hist[-6:-1]) and cur['close'] < cur['open']:
                signals.append(('COMPRESSION_EXPANSION','SELL',a))
    # De-duplicate strategy-direction pairs.
    unique=[]; seen=set()
    for s in signals:
        if (s[0],s[1]) not in seen: unique.append(s);seen.add((s[0],s[1]))
    return unique

def cost_r_scenarios():
    # Illustrative deductions, not observed Deriv spread/slippage. Override via env if broker measurements exist.
    raw=os.getenv('COST_SCENARIOS_R','0.02,0.05,0.10')
    vals=[]
    for x in raw.split(','):
        try:
            v=float(x.strip())
            if v>=0: vals.append(v)
        except ValueError: pass
    return sorted(set(vals or [0.02,0.05,0.10]))

def simulate(candles, i, direction, entry, stop_dist, horizon=30):
    sign=1 if direction=='BUY' else -1
    stop=entry-sign*stop_dist; targets=[entry+sign*stop_dist*r for r in (0.5,1.0,1.5)]
    hit=[False,False,False]; status='TIMEOUT'; terminal=0.0; exit_idx=min(i+horizon,len(candles)-1)
    for j in range(i+1, min(i+horizon+1,len(candles))):
        c=candles[j]
        stop_hit = c['low']<=stop if sign==1 else c['high']>=stop
        target_hit=[c['high']>=t if sign==1 else c['low']<=t for t in targets]
        hit=[old or new for old,new in zip(hit,target_hit)]
        # Conservative OHLC ordering: if stop and any target touch in same candle, count worst case as stop.
        if stop_hit:
            status='AMBIGUOUS_STOP_FIRST' if any(target_hit) else 'SL'; terminal=-1.0; exit_idx=j; break
        if target_hit[2]: status='TP3';terminal=1.5;exit_idx=j;break
        if target_hit[1]: status='TP2';terminal=1.0;exit_idx=j;break
        if target_hit[0]: status='TP1';terminal=0.5;exit_idx=j;break
    else:
        c=candles[exit_idx]
        terminal=max(-1.0,min(1.5,((c['close']-entry)*sign)/stop_dist))
    return {'status':status,'gross_r':round(terminal,5),'tp1':hit[0],'tp2':hit[1],'tp3':hit[2],'exit_ts':candles[exit_idx]['ts'],'stop':stop,'tp1_price':targets[0],'tp2_price':targets[1],'tp3_price':targets[2]}

def metrics(rows, cost_r):
    if not rows:return {'trades':0,'wins':0,'losses':0,'ambiguous':0,'win_rate_pct':None,'gross_total_R':0,'net_total_R':0,'avg_net_R':None,'profit_factor':None,'max_drawdown_R':0,'tp1_hit_pct':None,'tp2_hit_pct':None,'tp3_hit_pct':None}
    rs=[r['gross_r']-cost_r for r in rows]
    wins=sum(x>0 for x in rs); losses=sum(x<0 for x in rs)
    gross_profit=sum(x for x in rs if x>0); gross_loss=-sum(x for x in rs if x<0)
    eq=peak=dd=0.0
    for x in rs:
        eq+=x;peak=max(peak,eq);dd=max(dd,peak-eq)
    n=len(rows)
    return {'trades':n,'wins':wins,'losses':losses,'ambiguous':sum(r['status']=='AMBIGUOUS_STOP_FIRST' for r in rows),'win_rate_pct':round(wins/n*100,2),'gross_total_R':round(sum(r['gross_r'] for r in rows),3),'net_total_R':round(sum(rs),3),'avg_net_R':round(statistics.mean(rs),4),'profit_factor':round(gross_profit/gross_loss,3) if gross_loss>0 else ('INF' if gross_profit>0 else None),'max_drawdown_R':round(dd,3),'tp1_hit_pct':round(100*sum(r['tp1_hit'] for r in rows)/n,2),'tp2_hit_pct':round(100*sum(r['tp2_hit'] for r in rows)/n,2),'tp3_hit_pct':round(100*sum(r['tp3_hit'] for r in rows)/n,2)}

def backtest(symbol,candles,days):
    if len(candles)<1500: raise RuntimeError(f'Insufficient M1 candles: {len(candles)}. Require at least 1,500 after download.')
    m5=aggregate(candles,5);m15=aggregate(candles,15)
    # Map only completed HTF bars to each M1 timestamp (strictly less than current bar start).
    idx5=idx15=0; trades=[]; last_signal={}; horizon=int(os.getenv('HORIZON_M1_BARS','30')); cooldown=int(os.getenv('STRATEGY_COOLDOWN_M1','10'))
    warmup=max(300, int(len(candles)*0.03)); test_start=int(len(candles)*0.70)
    print(f'[BACKTEST] candles={len(candles)} warmup={warmup} train/test boundary={test_start} horizon={horizon} M1 bars',flush=True)
    for i in range(warmup, len(candles)-horizon-1):
        ts=candles[i]['ts']
        while idx5+1<len(m5) and m5[idx5+1]['ts']+300<=ts:idx5+=1
        while idx15+1<len(m15) and m15[idx15+1]['ts']+900<=ts:idx15+=1
        # Only completed M5/M15 candles are available to signal logic.
        h5=m5[:idx5+1] if m5 and m5[idx5]['ts']+300<=ts else m5[:idx5]
        h15=m15[:idx15+1] if m15 and m15[idx15]['ts']+900<=ts else m15[:idx15]
        sigs=make_signals(candles[max(0,i-300):i+1],h5[-100:],h15[-100:],len(candles[max(0,i-300):i+1])-1)
        for strat,direction,stop_dist in sigs:
            key=(strat,direction)
            if i-last_signal.get(key,-10**9)<cooldown:continue
            # Entry is next candle open to avoid entering at a close that was not executable until after it.
            entry=candles[i+1]['open']
            res=simulate(candles,i+1,direction,entry,stop_dist,horizon)
            row={'symbol':symbol,'strategy':strat,'direction':direction,'signal_ts':ts,'signal_utc':time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(ts)),'entry_ts':candles[i+1]['ts'],'entry':round(entry,5),'stop':round(res['stop'],5),'tp1_price':round(res['tp1_price'],5),'tp2_price':round(res['tp2_price'],5),'tp3_price':round(res['tp3_price'],5),'status':res['status'],'gross_r':res['gross_r'],'tp1_hit':res['tp1'],'tp2_hit':res['tp2'],'tp3_hit':res['tp3'],'exit_ts':res['exit_ts'],'sample':'OUT_OF_SAMPLE' if i>=test_start else 'IN_SAMPLE'}
            trades.append(row);last_signal[key]=i
        if (i-warmup)%5000==0: print(f'[BACKTEST] progress {i}/{len(candles)} signals recorded={len(trades)}',flush=True)
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    with (OUT_DIR/f'{symbol}_M1_history.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['ts','open','high','low','close']);w.writeheader();w.writerows(candles)
    fields=list(trades[0]) if trades else ['symbol','strategy','direction','signal_ts','signal_utc','entry_ts','entry','stop','tp1_price','tp2_price','tp3_price','status','gross_r','tp1_hit','tp2_hit','tp3_hit','exit_ts','sample']
    with (OUT_DIR/f'{symbol}_strategy_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(trades)
    costs=cost_r_scenarios(); strategies=sorted({r['strategy'] for r in trades})
    first=time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(candles[0]['ts']));last=time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(candles[-1]['ts']))
    summary={'symbol':symbol,'requested_days':days,'actual_candles':len(candles),'first_utc':first,'last_utc':last,'in_sample_candles':test_start,'out_of_sample_start_utc':time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(candles[min(test_start,len(candles)-1)]['ts'])),'horizon_m1_bars':horizon,'stop':'1 x M1 ATR(14) at signal close','targets_R':[0.5,1.0,1.5],'entry':'next M1 candle open after signal close','signal_context':'M1 with only fully completed M5/M15 candles','same_candle_rule':'stop-first, conservative when stop and target touch in same candle','cost_note':'No verified historical executable spread/slippage data available. Cost deductions below are hypothetical sensitivity scenarios, not measured broker costs.','cost_scenarios_R_per_trade':costs,'strategies':{}}
    for strat in strategies:
        allr=[r for r in trades if r['strategy']==strat]
        summary['strategies'][strat]={'ALL':{f'cost_{c:.3f}R':metrics(allr,c) for c in costs},'IN_SAMPLE':{f'cost_{c:.3f}R':metrics([r for r in allr if r['sample']=='IN_SAMPLE'],c) for c in costs},'OUT_OF_SAMPLE':{f'cost_{c:.3f}R':metrics([r for r in allr if r['sample']=='OUT_OF_SAMPLE'],c) for c in costs}}
    (OUT_DIR/f'{symbol}_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('\n'+'='*88,flush=True);print('QUINT CAPITAL V75 RESEARCH ENGINE — HISTORICAL BACKTEST',flush=True);print(f'SYMBOL={symbol} | CANDLES={len(candles)} | REQUESTED_DAYS={days}',flush=True);print(f'PERIOD_UTC={first} -> {last}',flush=True);print(f'ENTRY=next M1 open | CONTEXT=M5/M15 completed bars only | HORIZON={horizon} M1 bars | SL=1x ATR14 | TP=.5R/1R/1.5R',flush=True);print(f'COST SENSITIVITY deductions per trade (R): {costs}',flush=True);print('COST WARNING: These are hypothetical deductions. Historical executable spread/slippage has not been verified.',flush=True)
    for strat in strategies:
        print('\n'+strat,flush=True)
        for split in ('IN_SAMPLE','OUT_OF_SAMPLE'):
            print(f'  {split}',flush=True)
            rs=[r for r in trades if r['strategy']==strat and r['sample']==split]
            for c in costs:
                m=metrics(rs,c);print(f"    cost={c:.3f}R | n={m['trades']} win%={m['win_rate_pct']} avg_net_R={m['avg_net_R']} total_net_R={m['net_total_R']} PF={m['profit_factor']} maxDD_R={m['max_drawdown_R']} ambiguous={m['ambiguous']} TP1/2/3={m['tp1_hit_pct']}/{m['tp2_hit_pct']}/{m['tp3_hit_pct']}%",flush=True)
    print('\n[FILES] '+str(OUT_DIR),flush=True);print(f'[FILES] {symbol}_summary.json | {symbol}_strategy_results.csv | {symbol}_M1_history.csv',flush=True);print('='*88+'\n',flush=True)
    return summary

async def run_backtest(days=7):
    symbol,candles=await fetch_history(days)
    if not candles: raise RuntimeError('Deriv returned no usable candles')
    return backtest(symbol,candles,days)


# --- Railway launcher and live public tick monitor ---
#!/usr/bin/env python3
"""Railway entry point: automatic daily historical research, then public live tick heartbeat. No execution."""
import asyncio, json, os, time
from contextlib import asynccontextmanager
from pathlib import Path
import websockets

DATA_DIR=Path(os.getenv('DATA_DIR','/app/data'))
MARKER=DATA_DIR/'v75_research_last_success.json'
SYMBOL=os.getenv('DERIV_SYMBOL','R_75')
DEFAULT_WS_URLS=[
    _ensure_app_id(os.getenv('DERIV_WS_URL','wss://ws.derivws.com/websockets/v3?app_id=1089')),
    _ensure_app_id('wss://frontend.binaryws.com/websockets/v3?l=EN&app_id=1089'),
]
@asynccontextmanager
async def connect_deriv():
    errors=[]; seen=set(); ws=None
    for url in DEFAULT_WS_URLS:
        if not url or url in seen: continue
        seen.add(url)
        try:
            print(f'[CONNECTION] Trying Deriv endpoint: {url.split("?")[0]}',flush=True)
            ws=await websockets.connect(url,ping_interval=20,ping_timeout=20,close_timeout=10)
            print(f'[CONNECTION] Connected via {url.split("?")[0]}',flush=True)
            break
        except Exception as exc:
            errors.append(f'{url.split("?")[0]} => {type(exc).__name__}: {exc}')
            print(f'[CONNECTION][WARNING] Endpoint failed: {type(exc).__name__}: {exc}',flush=True)
    if ws is None:
        raise ConnectionError('All Deriv WebSocket endpoints failed. '+' | '.join(errors))
    try:
        yield ws
    finally:
        await ws.close()

def should_run():
    if os.getenv('AUTO_BACKTEST_ON_START','1').lower() in ('0','false','no','off'):
        print('[AUTO-BACKTEST] Disabled by AUTO_BACKTEST_ON_START',flush=True);return False
    hours=max(1,int(os.getenv('BACKTEST_MIN_INTERVAL_HOURS','24')))
    try:
        last=json.loads(MARKER.read_text()).get('last_success_epoch',0)
    except Exception:last=0
    due=time.time()-float(last)>=hours*3600
    print(f'[AUTO-BACKTEST] due={due} interval_hours={hours} marker={MARKER}',flush=True)
    return due

def mark_success(summary):
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    temp=MARKER.with_suffix('.tmp')
    temp.write_text(json.dumps({'last_success_epoch':int(time.time()),'symbol':summary.get('symbol'),'candles':summary.get('actual_candles')}),encoding='utf-8')
    temp.replace(MARKER)

async def live_heartbeat():
    """Live M1 scalping signal monitor with simulated outcomes; never executes trades."""
    delay=5
    candles=[]
    current=None
    active=[]
    stats={'setups':0,'wins':0,'losses':0,'timeouts':0,'ambiguous':0}
    log_dir=DATA_DIR/'scalping'
    log_dir.mkdir(parents=True,exist_ok=True)
    setup_file=log_dir/'v75_scalping_setups.jsonl'
    state_file=log_dir/'v75_scalping_state.json'

    def save_state():
        payload={**stats,'open_setups':len(active),'last_update_epoch':int(time.time()),'symbol':SYMBOL,
                 'mode':'ANALYSIS ONLY — NO TRADE EXECUTION','strategy':'M1 entry with completed M5/M15 confirmation',
                 'open':active}
        state_file.write_text(json.dumps(payload,indent=2),encoding='utf-8')

    def log_setup(row):
        with setup_file.open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,separators=(',',':'))+'\n')

    def close_setup(setup, status, price, epoch):
        sign=1 if setup['direction']=='BUY' else -1
        r=max(-1.0,min(1.5,((price-setup['entry'])*sign)/setup['risk_distance']))
        setup.update({'status':status,'exit':round(price,5),'exit_epoch':epoch,'terminal_R':round(r,4)})
        if r>0: stats['wins']+=1
        elif r<0: stats['losses']+=1
        else: stats['timeouts']+=1
        if status=='AMBIGUOUS': stats['ambiguous']+=1
        log_setup(setup)
        print(f"[SETUP-CLOSED] id={setup['id']} {setup['strategy']} {setup['direction']} status={status} R={r:+.2f} | W/L/T={stats['wins']}/{stats['losses']}/{stats['timeouts']}",flush=True)

    while True:
        try:
            async with connect_deriv() as ws:
                req={'ticks':SYMBOL,'subscribe':1,'req_id':8001}
                await ws.send(json.dumps(req))
                print(f'[SCALP-MONITOR] Connected; subscribed to {SYMBOL}. Building M1 candles; signals are simulated only.',flush=True)
                delay=5
                async for raw in ws:
                    msg=json.loads(raw)
                    if msg.get('error'):
                        raise RuntimeError(msg['error'].get('message','Deriv websocket error'))
                    if msg.get('msg_type')!='tick':
                        continue
                    tick=msg.get('tick',{})
                    try:
                        epoch=int(tick['epoch']); price=float(tick['quote'])
                    except (KeyError,TypeError,ValueError):
                        continue
                    minute=epoch-(epoch%60)
                    if current is None:
                        current={'ts':minute,'open':price,'high':price,'low':price,'close':price}
                    elif minute==current['ts']:
                        current['high']=max(current['high'],price);current['low']=min(current['low'],price);current['close']=price
                    elif minute>current['ts']:
                        # Only completed candles are used for signal decisions.
                        if minute-current['ts']<=180:
                            candles.append(current)
                            if len(candles)>20000: candles=candles[-20000:]
                            if len(candles)%5==0:
                                print(f"[SCALP-MONITOR] closed_M1={len(candles)} quote={price} open_setups={len(active)}",flush=True)
                            if len(candles)>=100:
                                m5=aggregate(candles,5);m15=aggregate(candles,15)
                                ts=current['ts']
                                m5=[c for c in m5 if c['ts']+300<=ts]
                                m15=[c for c in m15 if c['ts']+900<=ts]
                                signals=make_signals(candles,m5,m15,len(candles)-1)
                                if signals and not active:
                                    # Prioritize pullback, then momentum; reversals are lower priority.
                                    priority={'TREND_PULLBACK':0,'MOMENTUM_BREAKOUT':1,'COMPRESSION_EXPANSION':2,'FAILED_BREAK_REVERSAL':3,'RANGE_REJECTION':4}
                                    strat,direction,risk=sorted(signals,key=lambda x:priority.get(x[0],99))[0]
                                    entry=price
                                    sign=1 if direction=='BUY' else -1
                                    sid=f"{SYMBOL}-{epoch}-{stats['setups']+1}"
                                    setup={'id':sid,'symbol':SYMBOL,'strategy':strat,'direction':direction,'signal_epoch':epoch,
                                           'entry':round(entry,5),'risk_distance':round(risk,8),'stop':round(entry-sign*risk,5),
                                           'tp1':round(entry+sign*risk*0.5,5),'tp2':round(entry+sign*risk,5),
                                           'tp3':round(entry+sign*risk*1.5,5),'opened_epoch':epoch,'expires_epoch':epoch+1800,
                                           'status':'OPEN_SIMULATED','terminal_R':None}
                                    active.append(setup);stats['setups']+=1;log_setup(setup);save_state()
                                    print(f"[SCALP-SIGNAL] {direction} strategy={strat} entry={entry:.5f} SL={setup['stop']:.5f} TP1={setup['tp1']:.5f} TP2={setup['tp2']:.5f} TP3={setup['tp3']:.5f} | SIMULATED ONLY",flush=True)
                        current={'ts':minute,'open':price,'high':price,'low':price,'close':price}
                    else:
                        # Ignore out-of-order ticks for candle construction.
                        continue
                    # Tick-by-tick simulated position tracking. No order API is called.
                    for setup in list(active):
                        sign=1 if setup['direction']=='BUY' else -1
                        stop_hit=price<=setup['stop'] if sign==1 else price>=setup['stop']
                        tp3_hit=price>=setup['tp3'] if sign==1 else price<=setup['tp3']
                        tp2_hit=price>=setup['tp2'] if sign==1 else price<=setup['tp2']
                        tp1_hit=price>=setup['tp1'] if sign==1 else price<=setup['tp1']
                        if stop_hit:
                            close_setup(setup,'SL',price,epoch);active.remove(setup)
                        elif tp3_hit:
                            close_setup(setup,'TP3',price,epoch);active.remove(setup)
                        elif tp2_hit:
                            close_setup(setup,'TP2',price,epoch);active.remove(setup)
                        elif tp1_hit:
                            close_setup(setup,'TP1',price,epoch);active.remove(setup)
                        elif epoch>=setup['expires_epoch']:
                            close_setup(setup,'TIMEOUT',price,epoch);active.remove(setup)
                    if epoch%30==0: save_state()
        except Exception as exc:
            print(f'[SCALP-MONITOR][WARNING] {type(exc).__name__}: {exc}; reconnecting in {delay}s',flush=True)
            await asyncio.sleep(delay);delay=min(delay*2,60)

async def main():
    print('QUINT CAPITAL V75 SCALPING MONITOR v1.0',flush=True)
    print('ANALYSIS ONLY — NO TRADE EXECUTION — LIVE SIGNALS + SIMULATED SETUP TRACKING',flush=True)
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    (DATA_DIR/'scalping').mkdir(parents=True,exist_ok=True)
    print(f'[STORAGE] Persistent data directory: {DATA_DIR}; existing files will not be deleted.',flush=True)
    print(f'[CONFIG] symbol={SYMBOL} | entry=M1 closed candle | context=completed M5/M15 | SL=1x ATR14 | targets=0.5R/1R/1.5R | timeout=30 minutes',flush=True)
    print('[CONFIG] One simulated setup at a time. No orders are submitted.',flush=True)
    await live_heartbeat()

async def run():
    """Compatibility entry point for Railway's launcher.py (main.run())."""
    await main()

if __name__ == '__main__':
    asyncio.run(run())

