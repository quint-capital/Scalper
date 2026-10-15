import json
import math
from pathlib import Path
from config import (LEARNING_MODEL_FILE, LEARNING_MIN_RESOLVED,
                    LEARNING_MIN_GROUP_SAMPLES, LEARNING_MIN_BAD_GROUPS,
                    LEARNING_CONFIDENCE_Z)

MODEL_VERSION = "QUTE_ADAPTIVE_CONTEXT_LEARNER_V1"


def _band(value, edges, labels):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1] if labels else "UNKNOWN"


def feature_groups(setup):
    """Stable, human-readable contexts used for cautious online learning."""
    aligned = sum(setup.get(k) == setup.get("directional_trend")
                  for k in ("h4", "h1", "m30", "m15", "m5", "m1"))
    m1 = setup.get("m1", "UNKNOWN")
    m5 = setup.get("m5", "UNKNOWN")
    score = setup.get("structure_score")
    trigger = setup.get("trigger_score")
    confirms = int(setup.get("entry_confirmations") or 0)
    exhaustion = setup.get("exhaustion_level", "UNKNOWN")
    direction = setup.get("direction", "UNKNOWN")
    m1_zone = setup.get("m1_zone", "UNKNOWN")
    m15_zone = setup.get("m15_zone", "UNKNOWN")
    return {
        "direction": direction,
        "structure_band": _band(score, [55, 65, 75], ["LOW", "MID", "HIGH", "VERY_HIGH"]),
        "trigger_band": _band(trigger, [55, 70], ["LOW", "MID", "HIGH"]),
        "confirmations": _band(confirms, [2, 3], ["2_OR_LESS", "3", "4_PLUS"]),
        "trend_alignment": _band(aligned, [3, 5], ["LOW_0_2", "MID_3_4", "HIGH_5_6"]),
        "m1_m5_agreement": "AGREE" if m1 == m5 and m1 in ("BULLISH", "BEARISH") else "DISAGREE_OR_NEUTRAL",
        "exhaustion": exhaustion,
        "m15_location": m15_zone,
        "m1_location": m1_zone,
    }


class AdaptiveLearner:
    """Conservative online learner. It never edits entry, SL, TP1 or engine rules.

    It learns from every generated setup's shadow outcome, including setups it
    declined to track as active paper trades. A context is filtered only when
    multiple independently observed feature buckets show statistically cautious
    evidence of negative realized R. Until then, behavior is pass-through.
    """
    def __init__(self):
        self.state = {"version": MODEL_VERSION, "resolved_candidates": 0,
                      "seen_ids": [], "groups": {}, "last_decision": "WARMUP_PASS_THROUGH"}
        self._load()

    def _load(self):
        p = Path(LEARNING_MODEL_FILE)
        try:
            if p.exists():
                loaded = json.loads(p.read_text(encoding="utf-8"))
                if loaded.get("version") == MODEL_VERSION:
                    self.state.update(loaded)
        except Exception as exc:
            print(f"[LEARN][WARNING] Model load failed; starting safely: {exc}")

    def save(self):
        p = Path(LEARNING_MODEL_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self.state, separators=(",", ":")), encoding="utf-8")
        tmp.replace(p)

    def _bucket(self, feature, value):
        return self.state.setdefault("groups", {}).setdefault(f"{feature}={value}",
            {"n": 0, "sum_r": 0.0, "sum_sq_r": 0.0, "wins": 0, "losses": 0})

    def observe(self, setup):
        sid = setup.get("id")
        if not sid or sid in set(self.state.get("seen_ids", [])):
            return False
        if setup.get("outcome") not in ("TP1", "SL") or setup.get("realized_r") is None:
            return False
        realized = float(setup["realized_r"])
        features = setup.get("learning_features") or feature_groups(setup)
        for feature, value in features.items():
            bucket = self._bucket(feature, str(value))
            bucket["n"] += 1
            bucket["sum_r"] += realized
            bucket["sum_sq_r"] += realized * realized
            bucket["wins"] += int(setup.get("outcome") == "TP1")
            bucket["losses"] += int(setup.get("outcome") == "SL")
        self.state["resolved_candidates"] = int(self.state.get("resolved_candidates", 0)) + 1
        ids = self.state.setdefault("seen_ids", [])
        ids.append(sid)
        self.state["seen_ids"] = ids[-10000:]
        self.save()
        return True

    def evaluate(self, setup):
        features = setup.get("learning_features") or feature_groups(setup)
        n_total = int(self.state.get("resolved_candidates", 0))
        if n_total < LEARNING_MIN_RESOLVED:
            self.state["last_decision"] = f"WARMUP_PASS_THROUGH ({n_total}/{LEARNING_MIN_RESOLVED})"
            return True, self.state["last_decision"]
        bad = []
        for feature, value in features.items():
            b = self.state.get("groups", {}).get(f"{feature}={value}")
            if not b or int(b.get("n", 0)) < LEARNING_MIN_GROUP_SAMPLES:
                continue
            n = int(b["n"])
            mean = float(b["sum_r"]) / n
            if n > 1:
                variance = max(0.0, (float(b["sum_sq_r"]) - float(b["sum_r"])**2 / n) / (n - 1))
            else:
                variance = 0.0
            upper = mean + LEARNING_CONFIDENCE_Z * math.sqrt(variance / n)
            # Demand a negative expected result even at the cautious upper bound.
            if upper < -0.05:
                bad.append({"feature": feature, "value": value, "n": n,
                            "mean_r": round(mean, 3), "upper_r": round(upper, 3)})
        if len(bad) >= LEARNING_MIN_BAD_GROUPS:
            reason = "LEARNED_CONTEXT_FILTER: " + ", ".join(
                f"{x['feature']}={x['value']} n={x['n']} mean={x['mean_r']}R upper={x['upper_r']}R"
                for x in bad[:4])
            self.state["last_decision"] = reason
            self.save()
            return False, reason
        self.state["last_decision"] = f"PASS — no robust negative-context evidence ({len(bad)} bucket(s))"
        return True, self.state["last_decision"]

    def summary(self):
        groups = self.state.get("groups", {})
        weak = []
        for key, b in groups.items():
            n = int(b.get("n", 0))
            if n < LEARNING_MIN_GROUP_SAMPLES:
                continue
            mean = float(b["sum_r"]) / n
            weak.append((mean, key, n))
        weak.sort()
        weakest = "; ".join(f"{k}: {m:.2f}R / n={n}" for m, k, n in weak[:3]) or "not enough repeated evidence"
        return (f"ADAPTIVE LEARNER: resolved shadow candidates={self.state.get('resolved_candidates', 0)} | "
                f"groups={len(groups)} | last decision={self.state.get('last_decision', 'N/A')}\n"
                f"LEARNED CONTEXTS TO WATCH: {weakest}\n"
                "LEARNING SAFETY: baseline entry/SL/TP1 formulas unchanged; model only filters a setup after repeated negative-context evidence.")
