import asyncio
import json
import time
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass
from config import *
from data import DerivTicks
from engine import analyze, report
from alerts import send_telegram
from journal import (
    append_analysis, load_setups, save_setups, load_active, save_active,
    make_setup_record, update_setup, summarize_setups, performance_text, _setup_signature,
)

def storage_diagnostics():
    paths = [HISTORY_FILE, ANALYSIS_JOURNAL_FILE, SETUP_JOURNAL_FILE, ACTIVE_SETUPS_FILE]
    print(f"[STORAGE] Expected data directory: {DATA_DIR}")
    print(f"[STORAGE] RAILWAY_VOLUME_MOUNT_PATH: {os.getenv('RAILWAY_VOLUME_MOUNT_PATH', 'NOT SET')}")
    for path in paths:
        p = Path(path)
        print(f"[STORAGE] {path}: {'EXISTS' if p.exists() else 'MISSING'}" + (f" | bytes={p.stat().st_size}" if p.exists() else ""))
    try:
        marker = Path(STORAGE_MARKER_FILE)
        marker.parent.mkdir(parents=True, exist_ok=True)
        if not marker.exists():
            marker.write_text(f"created={int(time.time())}\n", encoding="utf-8")
            print(f"[STORAGE] Created volume marker: {marker}")
        else:
            print(f"[STORAGE] Volume marker found: {marker}")
    except Exception as exc:
        print(f"[STORAGE][WARNING] Cannot write persistent marker: {type(exc).__name__}: {exc}")

def aggregate(c, minutes):
    step=minutes*60; b={}
    for x in c:
        k=(x["ts"]//step)*step
        if k not in b:b[k]={"ts":k,"open":x["open"],"high":x["high"],"low":x["low"],"close":x["close"],"volume":x.get("volume",0)}
        else:
            b[k]["high"]=max(b[k]["high"],x["high"]); b[k]["low"]=min(b[k]["low"],x["low"]); b[k]["close"]=x["close"]; b[k]["volume"]+=x.get("volume",0)
    return [b[k] for k in sorted(b)]

def load():
    p=Path(HISTORY_FILE)
    try:return json.loads(p.read_text()) if p.exists() else []
    except Exception:return []

def save(c):
    p=Path(HISTORY_FILE); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(c[-MAX_M1_HISTORY:],separators=(",",":")))

def frames_from(history):
    return {"M1":history,"M5":aggregate(history,5),"M15":aggregate(history,15)}

def _journal_record(x, candle):
    r=x["readings"]
    return {
        "ts": int(candle["ts"]),
        "price": float(candle["close"]),
        "state": x["state"],
        "market_bias": x["direction"],
        "original_direction": x.get("original_direction", "UNKNOWN"),
        "strategy": "QUTE_V75_IMPROVED_REVERSED_V2_RESPONSIVE",
        "structure_score": x["structure_score"],
        "trigger_score": x["trigger_score"],
        "confidence": x["confidence"],
        "entry_quality": x["entry_quality"],
        "entry_timing_filter": x.get("entry_timing_filter", {}),
        "setup_family": "QUTE_V75_ENTRY_TIMING_EXPERIMENTAL_V1",
        "continuation_score": x.get("continuation_score", 0),
        "transition_score": x.get("transition_score", 0),
        "entry_confirmations": x["confirmation_count"],
        "confirmations": x["confirmations"],
        "conflicts": x["conflicts"],
        "setup": x["setup"],
        "timeframes": {t: {
            "trend": r[t]["trend"], "momentum": r[t]["momentum"], "bos": r[t]["bos"],
            "mss": r[t]["mss"], "displacement": r[t]["displacement"], "fvg": r[t]["fvg"],
            "liquidity": r[t]["liquidity"], "zone": r[t]["zone"],
            "extension": r[t]["extension"], "exhaustion": r[t]["exhaustion"], "volatility": r[t]["volatility"], "count": r[t]["count"]
        } for t in ("M15","M5","M1")}
    }

async def run():
    print("QUINT CAPITAL V75 REVERSED V3.12 — CONTINUOUS LIVE PAPER MONITOR")
    print("M15 CONTEXT + M5 SETUP + M1 TRIGGER | FRESH V3.12 JOURNAL | AUTO PAPER TRADES")
    print("LIVE DERIV V75 TICKS + CONTINUOUS SIMULATED TRADES — NO REAL ORDERS")
    storage_diagnostics()
    history=load(); print(f"[DATA] M1 history loaded: {len(history)}")
    setups=load_setups(); active=load_active()
    print(f"[JOURNAL] Analysis journal: {ANALYSIS_JOURNAL_FILE}")
    print(f"[JOURNAL] Setup history: {len(setups)} | Active setups: {len(active)}")
    last_state=None; last_alert=0; retry_delay=5; last_setup_sig=None; last_alert_setup_sig=None
    # v3.6: one tracked paper setup at a time, and one setup per structural move. A setup cycle
    # is consumed when a trade is created and cannot be reused until the market
    # leaves BUY/SELL SETUP state and forms a fresh trigger cycle.
    move_cycle_locked=False
    while True:
        client=DerivTicks()
        try:
            await client.connect(); retry_delay=5
            if len(history)<HISTORY_BOOTSTRAP_CANDLES:
                boot=await client.bootstrap_candles(HISTORY_BOOTSTRAP_CANDLES)
                merged={x["ts"]:x for x in history}
                for x in boot:merged[x["ts"]]=x
                history=[merged[k] for k in sorted(merged)][-MAX_M1_HISTORY:]; save(history)
                print(f"[DATA] Deep bootstrap loaded: {len(history)} M1 candles")
            await client.subscribe()
            print(f"[DATA] Live stream active: {DERIV_SYMBOL}", flush=True)
            current=None
            async for tick in client.stream():
                ts=(tick["epoch"]//60)*60; p=tick["quote"]
                if current is None: current={"ts":ts,"open":p,"high":p,"low":p,"close":p,"volume":1}; continue
                if ts==current["ts"]:
                    current["high"]=max(current["high"],p); current["low"]=min(current["low"],p); current["close"]=p; current["volume"]+=1; continue

                history.append(current); history=history[-MAX_M1_HISTORY:]; save(history)
                x=analyze(frames_from(history))
                # Post-loss cooldown and consecutive-loss brake. These controls
                # affect paper setup admission only; no broker action exists.
                recent_closed = sorted([z for z in setups if z.get("status") == "CLOSED" and z.get("outcome") in ("SL", "TP1")], key=lambda z: int(z.get("closed_ts") or 0))
                cooldown = REV3_POST_LOSS_COOLDOWN_MINUTES * 60
                last_closed = recent_closed[-1] if recent_closed else None
                if x.get("state") in ("BUY SETUP", "SELL SETUP") and last_closed and last_closed.get("outcome") == "SL" and int(current["ts"]) - int(last_closed.get("closed_ts") or 0) < cooldown:
                    x["state"] = f"WAIT — POST-LOSS COOLDOWN — {REV3_POST_LOSS_COOLDOWN_MINUTES}m"
                    x["setup"] = None
                consecutive_losses = 0
                for z in reversed(recent_closed):
                    if z.get("outcome") == "SL": consecutive_losses += 1
                    else: break
                loss_streak_cooldown = max(cooldown, 15 * 60)
                if (x.get("state") in ("BUY SETUP", "SELL SETUP") and
                    consecutive_losses >= REV3_MAX_CONSECUTIVE_LOSSES and last_closed and
                    int(current["ts"]) - int(last_closed.get("closed_ts") or 0) < loss_streak_cooldown):
                    x["state"] = f"WAIT — LOSS STREAK BRAKE — {consecutive_losses} consecutive losses; cooldown active"
                    x["setup"] = None
                print(report(x))
                print(performance_text(summarize_setups(setups + active)))
                print("-"*60)

                # Persist the complete analysis snapshot. This is append-only JSONL,
                # so Railway volume preserves the live decision history across deploys.
                append_analysis(_journal_record(x, current))

                # Update all open setups using only candles AFTER their creation.
                changed=False
                for s in active[:]:
                    if int(current["ts"]) <= int(s.get("created_ts", 0)):
                        continue
                    before=s.get("status")
                    update_setup(s, current)
                    if s.get("status") != before or s.get("tp1_hit"):
                        changed=True
                    if s.get("status") == "CLOSED":
                        setups.append(s); active.remove(s); changed=True
                        print(f"[ENTRY-TIMING OUTCOME] {s['id']} -> {s['outcome']} | PLANNED RR={s.get('planned_rr') if s.get('planned_rr') is not None else 'N/A'} | REALIZED R={s.get('realized_r', 'N/A')} | MFE={s['max_favorable']:.2f}R | MAE={s['max_adverse']:.2f}R | BARS={s.get('bars_observed', 0)}")
                if changed:
                    save_active(active); save_setups(setups)

                # v3.6: one active tracked paper setup at a time + one setup per structural move.
                # A changed SL/TP/entry signature inside the same move must NOT
                # create another trade. The market must first leave SETUP state,
                # then produce a genuinely fresh setup cycle.
                sig=_setup_signature(x)
                setup_state = x.get('state') in ('BUY SETUP','SELL SETUP')
                if not setup_state and not active:
                    if move_cycle_locked:
                        print('[MOVE] Previous setup cycle released — waiting for a fresh setup event')
                    move_cycle_locked=False
                    last_setup_sig=None

                can_open = (not active) and (not move_cycle_locked)
                if sig and can_open:
                    new_setup=make_setup_record(x, current)
                    active.append(new_setup); save_active(active)
                    last_setup_sig=sig
                    move_cycle_locked=True
                    print(f"[QUTE SETUP] {new_setup['id']} | DIRECTION={new_setup['direction']} | IMPROVED REVERSED-SIGNAL V2 RESPONSIVE")
                    print(f"[TRADE METRICS] ENTRY={new_setup['entry']:.5f} | SL={new_setup['sl']:.5f} | TP1={new_setup['tp1']:.5f} | RISK={new_setup['risk']:.5f} | REWARD={new_setup['reward_distance']:.5f} | PLANNED RR={new_setup['planned_rr']:.2f}:1")
                    print(f"[JOURNAL] Active setups: {len(active)} | Historical setups: {len(setups)}")
                elif sig and active:
                    print('[SETUP BLOCKED] Active trade already exists — no second trade allowed')
                elif sig and move_cycle_locked:
                    print('[SETUP BLOCKED] Same structural move already traded — waiting for a fresh move')

                summary=summarize_setups(setups + active)
                if changed:
                    print("[JOURNAL] OUTCOME UPDATE")
                    print(performance_text(summary))

                now=time.time()
                # v3.6: alerts are still tied to a genuinely fresh setup, never
                # to repeated signatures from the same structural move.
                alertable = x["state"] in ("BUY SETUP","SELL SETUP","WAIT — EXTREME VOLATILITY")
                new_setup_alert = bool(sig and sig != last_alert_setup_sig)
                state_alert = x["state"] != last_state
                if alertable and (new_setup_alert or state_alert) and now-last_alert>=ALERT_COOLDOWN_SECONDS:
                    if send_telegram(report(x)):print("[ALERT] Telegram sent")
                    last_state=x["state"]; last_alert=now
                    if sig: last_alert_setup_sig=sig
                current={"ts":ts,"open":p,"high":p,"low":p,"close":p,"volume":1}
        except Exception as exc:
            print(f"[ERROR] {type(exc).__name__}: {exc}"); await client.close(); print(f"[DATA] Reconnecting in {retry_delay}s..."); await asyncio.sleep(retry_delay); retry_delay=min(retry_delay*2,60)

if __name__=="__main__":asyncio.run(run())
