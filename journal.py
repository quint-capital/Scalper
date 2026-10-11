import json
import os
import time
from pathlib import Path

ANALYSIS_JOURNAL_FILE = os.getenv("ANALYSIS_JOURNAL_FILE", "/app/data/v75_analysis_history_v35.jsonl")
SETUP_JOURNAL_FILE = os.getenv("SETUP_JOURNAL_FILE", "/app/data/v75_setups_v35.json")
ACTIVE_SETUPS_FILE = os.getenv("ACTIVE_SETUPS_FILE", "/app/data/v75_active_setups_v35.json")
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
        int(s.get("tp3", 0) * 100),
    )


def make_setup_record(x, candle):
    s = x.get("setup") or {}
    direction = "BUY" if x.get("state") == "BUY SETUP" else "SELL"
    return {
        "id": f"V75-v35-{int(candle['ts'])}-{direction}",
        "created_ts": int(candle["ts"]),
        "direction": direction,
        "state_at_creation": x.get("state"),
        "entry": float(s.get("entry")),
        "sl": float(s.get("sl")),
        "tp1": float(s.get("tp1")),
        "tp2": float(s.get("tp2")),
        "tp3": float(s.get("tp3")),
        "risk": float(s.get("risk")),
        "rr": [float(s.get("tp1_rr", 0.75)), 1.25, 1.75],
        "tp1_rr": float(s.get("tp1_rr", 0.75)),
        "tp2_rr": 1.25,
        "tp3_rr": 1.75,
        "tp1_basis": s.get("tp1_basis", "1.25R fallback"),
        "sl_basis": s.get("sl_basis", "M1/M5 local invalidation"),
        "structure_score": x.get("structure_score"),
        "trigger_score": x.get("trigger_score"),
        "confidence": x.get("confidence"),
        "entry_confirmations": x.get("confirmation_count", 0),
        "setup_type": x.get("setup_type", "NONE"),
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
        "tp2_hit": False,
        "tp3_hit": False,
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
    entry = setup["entry"]
    risk = setup["risk"]
    high = float(candle["high"]); low = float(candle["low"])
    setup["bars_observed"] = int(setup.get("bars_observed", 0)) + 1

    if direction == "BUY":
        favorable = max(0.0, high - entry)
        adverse = max(0.0, entry - low)
        hit1 = high >= setup["tp1"]; hit2 = high >= setup["tp2"]; hit3 = high >= setup["tp3"]
        hit_sl = low <= setup["sl"]
    else:
        favorable = max(0.0, entry - low)
        adverse = max(0.0, high - entry)
        hit1 = low <= setup["tp1"]; hit2 = low <= setup["tp2"]; hit3 = low <= setup["tp3"]
        hit_sl = high >= setup["sl"]

    setup["max_favorable"] = max(float(setup.get("max_favorable", 0)), favorable / risk if risk else 0)
    setup["max_adverse"] = max(float(setup.get("max_adverse", 0)), adverse / risk if risk else 0)
    setup["tp1_hit"] = bool(setup.get("tp1_hit") or hit1)
    setup["tp2_hit"] = bool(setup.get("tp2_hit") or hit2)
    setup["tp3_hit"] = bool(setup.get("tp3_hit") or hit3)

    # TP1 is the official research exit. If TP1 and SL are both touched in the
    # same M1 candle, OHLC data cannot reveal the intrabar order, so classify it
    # as ambiguous rather than inventing an order. Otherwise the first relevant
    # boundary reached determines the outcome. TP2/TP3 remain measurement
    # milestones only because the setup closes at TP1.
    if hit_sl and hit1:
        setup["status"] = "CLOSED"
        setup["outcome"] = "AMBIGUOUS_SL_AND_TARGET_SAME_CANDLE"
        setup["closed_ts"] = int(candle["ts"])
    elif hit_sl:
        setup["status"] = "CLOSED"
        setup["outcome"] = "SL"
        setup["closed_ts"] = int(candle["ts"])
    elif hit1:
        setup["status"] = "CLOSED"
        setup["outcome"] = "TP1"
        setup["closed_ts"] = int(candle["ts"])
    return setup


def summarize_setups(setups):
    closed = [s for s in setups if s.get("status") == "CLOSED"]
    terminal = [s for s in closed if s.get("outcome") in ("SL", "TP1", "TP2", "TP3")]
    wins = [s for s in terminal if s.get("outcome", "").startswith("TP")]
    losses = [s for s in terminal if s.get("outcome") == "SL"]
    ambiguous = [s for s in closed if s.get("outcome") == "AMBIGUOUS_SL_AND_TARGET_SAME_CANDLE"]
    tp1 = sum(bool(s.get("tp1_hit")) for s in setups)
    tp2 = sum(bool(s.get("tp2_hit")) for s in setups)
    tp3 = sum(bool(s.get("tp3_hit")) for s in setups)
    buy = sum(s.get("direction") == "BUY" for s in setups)
    sell = sum(s.get("direction") == "SELL" for s in setups)
    realized_r = []
    for s in terminal:
        outcome = s.get("outcome")
        if outcome == "SL":
            realized_r.append(-1.0)
        elif outcome == "TP1":
            realized_r.append(float(s.get("tp1_rr", 0.75)))
        elif outcome == "TP2":
            realized_r.append(float(s.get("tp2_rr", 1.25)))
        elif outcome == "TP3":
            realized_r.append(float(s.get("tp3_rr", 1.75)))
    avg_r = sum(realized_r) / len(realized_r) if realized_r else None
    return {
        "total": len(setups), "open": sum(s.get("status") == "OPEN" for s in setups),
        "closed": len(closed), "terminal": len(terminal), "wins": len(wins),
        "losses": len(losses), "ambiguous": len(ambiguous),
        "win_rate": (len(wins) / len(terminal) * 100) if terminal else None,
        "tp1_hit": tp1, "tp2_hit": tp2, "tp3_hit": tp3,
        "buy": buy, "sell": sell, "avg_r": avg_r,
    }

def performance_text(summary):
    def pct(v):
        return "N/A" if v is None else f"{v:.1f}%"
    def rr(v):
        return "N/A" if v is None else f"{v:+.2f}R"
    return (
        "QUINT CAPITAL V75 PERFORMANCE\n"
        "--------------------------------\n"
        f"SETUPS: {summary['total']} | OPEN: {summary['open']} | CLOSED: {summary['closed']}\n"
        f"WINS: {summary['wins']} | LOSSES: {summary['losses']} | AMBIGUOUS: {summary['ambiguous']}\n"
        f"WIN RATE: {pct(summary['win_rate'])} | AVG TERMINAL R: {rr(summary['avg_r'])}\n"
        f"TP1 HIT: {summary['tp1_hit']} | TP2 HIT: {summary['tp2_hit']} | TP3 HIT: {summary['tp3_hit']}\n"
        f"BUY SETUPS: {summary['buy']} | SELL SETUPS: {summary['sell']}"
    )
