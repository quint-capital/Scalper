import unittest
from engine import _market_regime, _improved_entry_confirmation

class ImprovedFilterTests(unittest.TestCase):
    def test_bullish_regime_uses_lower_three_only(self):
        r = {tf: {"trend": "BULLISH"} for tf in ("M15", "M5", "M1")}
        # Opposing higher-timeframe data must not affect the lower-three result.
        r.update({tf: {"trend": "BEARISH"} for tf in ("H4", "H1", "M30")})
        self.assertEqual(_market_regime(r)["label"], "LOWER-TF BULLISH TREND")
        self.assertFalse(_market_regime(r)["range_risk"])

    def test_bearish_regime_uses_lower_three_only(self):
        r = {tf: {"trend": "BEARISH"} for tf in ("M15", "M5", "M1")}
        self.assertEqual(_market_regime(r)["label"], "LOWER-TF BEARISH TREND")

    def test_mixed_lower_regime_flags_range_risk(self):
        r = {"M15":{"trend":"NEUTRAL"}, "M5":{"trend":"BULLISH"}, "M1":{"trend":"NEUTRAL"},
             "H4":{"trend":"BULLISH"}, "H1":{"trend":"BULLISH"}, "M30":{"trend":"BULLISH"}}
        self.assertTrue(_market_regime(r)["range_risk"])

    def test_confirmation_requires_close_structure_and_m5_support(self):
        frames = {"M1": [{"open": 1, "close": 2}] * 8}
        readings = {"M1":{"mss":"BULLISH","bos":"NONE","displacement":"NONE","momentum":"NONE"},
                    "M5":{"momentum":"BULLISH","mss":"NONE","bos":"NONE","displacement":"NONE"}}
        self.assertTrue(_improved_entry_confirmation(frames, readings, "BULLISH")["valid"])
        readings["M5"]["momentum"] = "BEARISH"
        self.assertFalse(_improved_entry_confirmation(frames, readings, "BULLISH")["valid"])

    def test_reversed_direction_needs_its_own_confirmation(self):
        frames = {"M1": [{"open": 2, "close": 1}] * 8}
        readings = {"M1":{"mss":"BEARISH","bos":"NONE","displacement":"NONE","momentum":"BEARISH"},
                    "M5":{"momentum":"BEARISH","mss":"NONE","bos":"NONE","displacement":"NONE"}}
        self.assertTrue(_improved_entry_confirmation(frames, readings, "BEARISH")["valid"])
        self.assertFalse(_improved_entry_confirmation(frames, readings, "BULLISH")["valid"])

if __name__ == "__main__":
    unittest.main()
