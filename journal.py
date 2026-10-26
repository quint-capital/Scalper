import json
import os
import time
from pathlib import Path

# Isolated journal namespace for the structure-led exit model. Do not reuse
# legacy journal environment variables or files from previous exit logic.
ANALYSIS_JOURNAL_FILE = os.getenv("REV3_ANALYSIS_JOURNAL_FILE", "/app/data/qute_v75_improved_reversed_v3_9_analysis.jsonl")
SETUP_JOURNAL_FILE = os.getenv("REV3_SETUP_JOURNAL_FILE", "/app/data/qute_v75_improved_reversed_v3_9_setups.json")
ACTIVE_SETUPS_FILE = os.getenv("REV3_ACTIVE_SETUPS_FILE", "/app/data/qute_v75_improved_reversed_v3_9_active.json")
MAX_ANALYSIS_JOURNAL_BYTES = int(os.getenv("MAX_ANALYSIS_JOURNAL_BYTES", str(25 * 1024 * 1024)))
MAX_SETUP_HISTORY = int(os.getenv("MAX_SETUP_HISTORY", "5000"))


def _ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _rotate_if_needed(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size < MAX_ANALYSIS_JOURNAL_BYTES:
        return
    rotated = p.with_name(p.name + ".1")
    try:
        if rotated.exists():
            rotated.unlink()
        p.rename(rotated)
    except Exception:
        pass


def append_analysis(record):
    _ensure_parent(ANALYSIS_JOURNAL_FILE)
    _rotate_if_needed(ANALYSIS_JOURNAL_FILE)
    with open(ANALYSIS_JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def _read_json(path, default):
    p = Path(path)
    try:
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path, data):
    _ensure_parent(path)
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def load_setups():
    data = _read_json(SETUP_JOURNAL_FILE, [])
    return data if isinstance(data, list) else []


def save_setups(setups):
    _write_json(SETUP_JOURNAL_FILE, setups[-MAX_SETUP_HISTORY:])


def load_active():
    data = _read_json(ACTIVE_SETUPS_FILE, [])
    return data if isinstance(data, list) else []


def save_active(active):
    _write_json(ACTIVE_SETUPS_FILE, active)


def _setup_signature(x):
    s = x.get("setup") or {}
    if x.get("state") not in ("BUY SETUP", "SELL SETUP") or not s:
        return None
    return "{}|{}|{}|{}".format(
        x.get("state"),
        int(s.get("entry", 0) * 100),
        int(s.get("sl", 0) * 100),
        int(s.get("tp1", 0) * 100),
    )


def make_setup_record(x, candle):
    s = x.get("setup") or {}
    direction = "BUY" if x.get("state") == "BUY SETUP" else "SELL"
    return {
        "id": f"V75-IMPROVED-REVERSED-V3_9-{int(candle['ts'])}-{direction}-{int(round(float(s.get('entry', 0))*100))}",
        "created_ts": int(candle["ts"]),
        "direction": direction,
        "state_at_creation": x.get("state"),
        "strategy": "QUTE_V75_IMPROVED_REVERSED_V2_RESPONSIVE",
        "original_direction": s.get("source_direction", s.get("original_direction", "UNKNOWN")),
        "emitted_direction": s.get("emitted_direction", direction),
        "entry": float(s.get("entry")),
        "sl": float(s.get("sl")),
        "tp1": float(s.get("tp1")),
        "original_sl": s.get("original_sl"),
        "original_tp1": s.get("original_tp1"),
        "risk": abs(float(s.get("entry")) - float(s.get("sl"))),
        "reward_distance": abs(float(s.get("tp1")) - float(s.get("entry"))),
        "planned_rr": (abs(float(s.get("tp1")) - float(s.get("entry"))) / abs(float(s.get("entry")) - float(s.get("sl")))) if abs(float(s.get("entry")) - float(s.get("sl"))) > 0 else None,
        "tp1_basis": s.get("tp1_basis", "structural TP1"),
        "sl_basis": s.get("sl_basis", "source TP1 restored as target geometry"),
        "structure_score": x.get("structure_score"),
        "trigger_score": x.get("trigger_score"),
        "confidence": x.get("confidence"),
        "entry_confirmations": x.get("confirmation_count", 0),
        "entry_timing_filter": x.get("entry_timing_filter", {}),
        "market_regime": x.get("market_regime", {}),
        "regime_gate": x.get("regime_gate", {}),
        "improved_confirmation_gate": x.get("improved_confirmation_gate", {}),
        "signal_mode": x.get("signal_mode", "QUTE_V75_IMPROVED_REVERSED_V2_RESPONSIVE"),
        "setup_family": "QUTE_V75_IMPROVED_REVERSED_V2_RESPONSIVE",
        "continuation_score": x.get("continuation_score", 0),
        "exhaustion_score": x.get("exhaustion_score", 0),
        "exhaustion_level": x.get("exhaustion_level", "NORMAL"),
        "exhaustion_reasons": x.get("exhaustion_reasons", []),
        "confirmations": x.get("confirmations", []),
        "conflicts": x.get("conflicts", []),
        "h4": x["readings"]["H4"]["trend"],
        "h1": x["readings"]["H1"]["trend"],
        "m30": x["readings"]["M30"]["trend"],
        "m15": x["readings"]["M15"]["trend"],
        "m5": x["readings"]["M5"]["trend"],
        "m1": x["readings"]["M1"]["trend"],
        "status": "OPEN",
        "tp1_hit": False,
        "max_favorable": 0.0,
        "max_adverse": 0.0,
        "outcome": None,
        "closed_ts": None,
        "bars_observed": 0,
    }


def update_setup(setup, candle):
    if setup.get("status") != "OPEN":
        return setup
    direction = setup["direction"]
    entry = float(setup["entry"])
    risk = float(setup["risk"])
    high = float(candle["high"]); low = float(candle["low"])
    target = float(setup["tp1"])
    stop = float(setup["sl"])
    setup["bars_observed"] = int(setup.get("bars_observed", 0)) + 1

    if direction == "BUY":
        favorable = max(0.0, high - entry)
        adverse = max(0.0, entry - low)
        hit_target = high >= target
        hit_sl = low <= stop
    else:
        favorable = max(0.0, entry - low)
        adverse = max(0.0, high - entry)
        hit_target = low <= target
        hit_sl = high >= stop

    setup["max_favorable"] = max(float(setup.get("max_favorable", 0)), favorable / risk if risk else 0)
    setup["max_adverse"] = max(float(setup.get("max_adverse", 0)), adverse / risk if risk else 0)
    setup["tp1_hit"] = bool(setup.get("tp1_hit") or hit_target)

    # If stop and target both occur inside the same M1 candle, OHLC cannot
    # establish which happened first. Preserve the ambiguity instead of guessing.
    if hit_sl and hit_target:
        setup["status"] = "CLOSED"
        setup["outcome"] = "AMBIGUOUS_SL_AND_TP1_SAME_CANDLE"
        setup["realized_r"] = None
        setup["closed_ts"] = int(candle["ts"])
    elif hit_sl:
        setup["status"] = "CLOSED"
        setup["outcome"] = "SL"
        setup["realized_r"] = -1.0
        setup["closed_ts"] = int(candle["ts"])
    elif hit_target:
        setup["status"] = "CLOSED"
        setup["outcome"] = "TP1"
        setup["realized_r"] = setup.get("planned_rr")
        setup["closed_ts"] = int(candle["ts"])
    return setup


def summarize_setups(setups):
    closed = [s for s in setups if s.get("status") == "CLOSED"]
    terminal = [s for s in closed if s.get("outcome") in ("SL", "TP1")]
    wins = [s for s in terminal if s.get("outcome") == "TP1"]
    losses = [s for s in terminal if s.get("outcome") == "SL"]
    ambiguous = [s for s in closed if s.get("outcome") == "AMBIGUOUS_SL_AND_TP1_SAME_CANDLE"]
    rr_values = [float(s["planned_rr"]) for s in setups if s.get("planned_rr") is not None]
    realized = [float(s["realized_r"]) for s in terminal if s.get("realized_r") is not None]
    gross_profit_r = sum(v for v in realized if v > 0)
    gross_loss_r = abs(sum(v for v in realized if v < 0))

    # "Points" are raw V75 index-price units: absolute price distances,
    # not cash P/L and not a broker-specific tick-value calculation.
    profit_points, loss_points = [], []
    for s in terminal:
        try:
            entry, stop, target = float(s["entry"]), float(s["sl"]), float(s["tp1"])
            if s.get("outcome") == "TP1":
                profit_points.append(abs(target - entry))
            elif s.get("outcome") == "SL":
                loss_points.append(abs(entry - stop))
        except (KeyError, TypeError, ValueError):
            # Ignore legacy/incomplete records instead of inventing a result.
            continue
    gross_profit_points = sum(profit_points)
    gross_loss_points = sum(loss_points)
    net_points = gross_profit_points - gross_loss_points
    point_trade_count = len(profit_points) + len(loss_points)

    return {
        "total": len(setups), "open": sum(s.get("status") == "OPEN" for s in setups),
        "closed": len(closed), "terminal": len(terminal), "wins": len(wins),
        "losses": len(losses), "ambiguous": len(ambiguous),
        "win_rate": (len(wins) / len(terminal) * 100) if terminal else None,
        "tp1_hit": sum(bool(s.get("tp1_hit")) for s in setups),
        "avg_planned_rr": (sum(rr_values) / len(rr_values)) if rr_values else None,
        "median_planned_rr": (sorted(rr_values)[len(rr_values)//2] if len(rr_values)%2 else (sorted(rr_values)[len(rr_values)//2-1] + sorted(rr_values)[len(rr_values)//2]) / 2) if rr_values else None,
        "avg_realized_r": (sum(realized) / len(realized)) if realized else None,
        "net_r": sum(realized),
        "profit_factor_r": (gross_profit_r / gross_loss_r) if gross_loss_r else (float("inf") if gross_profit_r else None),
        "gross_profit_r": gross_profit_r, "gross_loss_r": gross_loss_r,
        "avg_mfe_r": (sum(float(s.get("max_favorable", 0)) for s in terminal) / len(terminal)) if terminal else None,
        "avg_mae_r": (sum(float(s.get("max_adverse", 0)) for s in terminal) / len(terminal)) if terminal else None,
        "gross_profit_points": gross_profit_points,
        "gross_loss_points": gross_loss_points,
        "net_points": net_points,
        "point_trade_count": point_trade_count,
        "avg_net_points_per_trade": (net_points / point_trade_count) if point_trade_count else None,
    }


def performance_text(summary):
    def pct(v):
        return "N/A" if v is None else f"{v:.1f}%"
    def num(v, suffix=""):
        if v is None: return "N/A"
        if isinstance(v, float) and v == float("inf"): return "∞"
        return f"{v:.2f}{suffix}"
    return (
        "QUTE V75 SCALPER — UNIFIED STRATEGY PERFORMANCE | PAPER ONLY\n"
        "--------------------------------\n"
        f"SETUPS: {summary['total']} | OPEN: {summary['open']} | CLOSED: {summary['closed']} | AMBIGUOUS: {summary['ambiguous']}\n"
        f"WINS: {summary['wins']} | LOSSES: {summary['losses']} | WIN RATE: {pct(summary['win_rate'])}\n"
        f"PLANNED RR (AVG / MEDIAN): {num(summary['avg_planned_rr'])}:1 / {num(summary['median_planned_rr'])}:1\n"
        f"R METRICS (SECONDARY): NET {num(summary['net_r'])}R | AVG {num(summary['avg_realized_r'])}R per resolved trade | PF {num(summary['profit_factor_r'])}\n"
        f"POINTS — GROSS PROFIT: {num(summary['gross_profit_points'])} | GROSS LOSS: {num(summary['gross_loss_points'])} | NET: {num(summary['net_points'])}\n"
        f"POINTS — AVG NET PER RESOLVED TRADE: {num(summary['avg_net_points_per_trade'])} | POINT-COUNTED TRADES: {summary['point_trade_count']}\n"
        f"AVERAGE MFE / MAE: {num(summary['avg_mfe_r'])}R / {num(summary['avg_mae_r'])}R\n"
        f"TP1 HIT: {summary['tp1_hit']}"
    )
