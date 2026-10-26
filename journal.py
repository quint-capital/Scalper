import json
import os
import time
from pathlib import Path

ANALYSIS_JOURNAL_FILE = os.getenv("ANALYSIS_JOURNAL_FILE", "/app/data/v75_reverse_current_v3_analysis.jsonl")
SETUP_JOURNAL_FILE = os.getenv("SETUP_JOURNAL_FILE", "/app/data/v75_reverse_current_v3_setups.json")
ACTIVE_SETUPS_FILE = os.getenv("ACTIVE_SETUPS_FILE", "/app/data/v75_reverse_current_v3_active.json")
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
    if x.get("state") not in ("BUY SETUP", "SELL SETUP"):
        raise ValueError("Cannot create inverse paper setup without BUY/SELL SETUP state")

    # REVERSE-OF-CURRENT EXPERIMENT: invert the setup emitted by the current
    # strategy. BUY becomes SELL and SELL becomes BUY. Swap the current setup's
    # TP1 and SL prices exactly; do not widen targets or recalculate levels.
    source_direction = "BUY" if x.get("state") == "BUY SETUP" else "SELL"
    direction = "SELL" if source_direction == "BUY" else "BUY"
    entry = float(s.get("entry"))
    source_sl = float(s.get("sl"))
    source_tp1 = float(s.get("tp1"))
    inverse_sl = source_tp1
    inverse_tp1 = source_sl
    risk = abs(entry - inverse_sl)
    reward = abs(inverse_tp1 - entry)
    planned_rr = (reward / risk) if risk else None

    # Guard against malformed geometry rather than silently recording a setup
    # whose stop/target lie on the wrong side of the entry.
    valid_geometry = (
        inverse_sl > entry and inverse_tp1 < entry if direction == "SELL"
        else inverse_sl < entry and inverse_tp1 > entry
    )
    if not valid_geometry:
        geometry_note = "CHECK_GEOMETRY"
    else:
        geometry_note = "VALID"

    return {
        "id": f"V75-REVERSE-V3-{int(candle['ts'])}-{direction}",
        "created_ts": int(candle["ts"]),
        "direction": direction,
        "source_direction": source_direction,
        "state_at_creation": x.get("state"),
        "signal_mode": "REVERSE_OF_CURRENT_DOUBLE_REVERSED_BASELINE",
        "exit_model": "INVERT_DIRECTION_AND_SWAP_CURRENT_TP1_SL_EXACTLY",
        "source_sl": source_sl,
        "source_tp1": source_tp1,
        "entry": entry,
        "sl": inverse_sl,
        "tp1": inverse_tp1,
        "risk": risk,
        "planned_reward_points": reward,
        "planned_rr": round(planned_rr, 5) if planned_rr is not None else None,
        "geometry_check": geometry_note,
        "original_direction": s.get("original_direction", "UNKNOWN"),
        "original_sl": s.get("original_sl"),
        "original_tp1": s.get("original_tp1"),
        "tp1_basis": "Current setup SL swapped to inverse TP1",
        "sl_basis": "Current setup TP1 swapped to inverse SL",
        "structure_score": x.get("structure_score"),
        "trigger_score": x.get("trigger_score"),
        "confidence": x.get("confidence"),
        "entry_confirmations": x.get("confirmation_count", 0),
        "setup_type": x.get("setup_type", "REVERSE_OF_CURRENT"),
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
        "realized_points": None,
        "realized_r": None,
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
        setup["closed_ts"] = int(candle["ts"])
    elif hit_sl:
        setup["status"] = "CLOSED"
        setup["outcome"] = "SL"
        setup["realized_points"] = -abs(entry - stop)
        setup["realized_r"] = (setup["realized_points"] / risk) if risk else None
        setup["closed_ts"] = int(candle["ts"])
    elif hit_target:
        setup["status"] = "CLOSED"
        setup["outcome"] = "TP1"
        reward = abs(target - entry)
        setup["realized_points"] = reward
        setup["realized_r"] = (reward / risk) if risk else None
        setup["closed_ts"] = int(candle["ts"])
    if setup.get("outcome") == "AMBIGUOUS_SL_AND_TP1_SAME_CANDLE":
        setup["realized_points"] = None
        setup["realized_r"] = None
    return setup


def summarize_setups(setups):
    closed = [s for s in setups if s.get("status") == "CLOSED"]
    terminal = [s for s in closed if s.get("outcome") in ("SL", "TP1")]
    wins = [s for s in terminal if s.get("outcome") == "TP1"]
    losses = [s for s in terminal if s.get("outcome") == "SL"]
    ambiguous = [s for s in closed if s.get("outcome") == "AMBIGUOUS_SL_AND_TP1_SAME_CANDLE"]
    tp1 = sum(bool(s.get("tp1_hit")) for s in setups)
    buy = sum(s.get("direction") == "BUY" for s in setups)
    sell = sum(s.get("direction") == "SELL" for s in setups)
    realized = [float(s["realized_points"]) for s in terminal if s.get("realized_points") is not None]
    gross_profit_points = sum(v for v in realized if v > 0)
    gross_loss_points = sum(v for v in realized if v < 0)
    net_points = sum(realized)
    net_r = sum(float(s.get("realized_r") or 0) for s in terminal if s.get("realized_r") is not None)
    return {
        "total": len(setups), "open": sum(s.get("status") == "OPEN" for s in setups),
        "closed": len(closed), "terminal": len(terminal), "wins": len(wins),
        "losses": len(losses), "ambiguous": len(ambiguous),
        "win_rate": (len(wins) / len(terminal) * 100) if terminal else None,
        "tp1_hit": tp1, "buy": buy, "sell": sell,
        "gross_profit_points": gross_profit_points,
        "gross_loss_points": gross_loss_points,
        "net_points": net_points, "net_r": net_r,
        "points_counted": len(realized),
    }


def performance_text(summary):
    def pct(v):
        return "N/A" if v is None else f"{v:.1f}%"
    return (
        "QUINT CAPITAL V75 EXIT INTELLIGENCE V2 PERFORMANCE — PAPER ONLY\\n"
        "--------------------------------\\n"
        f"SETUPS: {summary['total']} | OPEN: {summary['open']} | CLOSED: {summary['closed']}\\n"
        f"WINS: {summary['wins']} | LOSSES: {summary['losses']} | AMBIGUOUS: {summary['ambiguous']}\\n"
        f"WIN RATE: {pct(summary['win_rate'])}\\n"
        f"TP1 HIT: {summary['tp1_hit']}\\n"
        f"GROSS PROFIT: +{summary['gross_profit_points']:.2f} points\\n"
        f"GROSS LOSS: {summary['gross_loss_points']:.2f} points\\n"
        f"NET PROFIT/LOSS: {summary['net_points']:+.2f} points | NET R: {summary['net_r']:+.2f}R\\n"
        f"POINTS COUNTED: {summary['points_counted']} terminal outcomes (ambiguous excluded)\\n"
        f"BUY SETUPS: {summary['buy']} | SELL SETUPS: {summary['sell']}"
    )
