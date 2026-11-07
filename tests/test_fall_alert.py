"""S2 fall alert tests."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fall_alert as fa  # noqa: E402

IST = fa.IST
NOW = datetime(2026, 11, 9, 13, 30, tzinfo=IST)
TODAY = "2026-11-09"
BANNED = ("buy now", "sell", "recommend", "will recover", "guarantee", "target")


def data(nifty_r1d, vix_r1d=2.0, asof=TODAY):
    return {"updated": "2026-11-09T07:45:00+00:00", "groups": {
        "global": [{"symbol": "^NSEI", "name": "NIFTY 50", "last": 24420.5, "r1d": nifty_r1d, "asof": asof}],
        "risk": [{"symbol": "^INDIAVIX", "name": "India VIX", "last": 19.8, "r1d": vix_r1d, "asof": asof}],
        "sectors": [{"symbol": "a", "name": "NIFTY Realty", "r1d": -4.1}, {"symbol": "b", "name": "NIFTY IT", "r1d": -1.0}],
    }}


class FallAlertTests(unittest.TestCase):
    def test_no_alert_on_small_fall(self):
        self.assertIsNone(fa.check(data(-1.5), {}, NOW))

    def test_alert_once_per_level(self):
        alert = fa.check(data(-2.4), {}, NOW)
        self.assertEqual(alert["keys"], ["nifty-2"])
        state = {"sent": {TODAY: alert["keys"]}}
        self.assertIsNone(fa.check(data(-2.8), state, NOW))           # तीच पातळी → पुन्हा नाही
        self.assertEqual(fa.check(data(-3.2), state, NOW)["keys"], ["nifty-3"])  # पुढची पातळी

    def test_jump_marks_all_crossed_levels(self):
        self.assertEqual(fa.check(data(-4.5), {}, NOW)["keys"], ["nifty-2", "nifty-3", "nifty-4"])

    def test_old_data_ignored(self):
        self.assertIsNone(fa.check(data(-5.0, 30.0, asof="2026-11-06"), {}, NOW))  # सुट्टी / जुना डेटा

    def test_vix_only_alert_uses_volatility_draft(self):
        alert = fa.check(data(-0.5, vix_r1d=18.0), {}, NOW)
        self.assertEqual(alert["keys"], ["vix+15"])
        self.assertIn("volatility has risen", alert["text"])

    def test_message_content_and_compliance(self):
        text = fa.check(data(-2.4), {}, NOW)["text"]
        self.assertIn("NIFTY 50: -2.40%", text)
        self.assertIn("1:15 PM", text)                 # updated 07:45 UTC = 13:15 IST
        self.assertIn("ARN-151469", text)
        self.assertIn("subject to market risks", text)
        self.assertIn("Weakest sectors: NIFTY Realty -4.10%", text)
        for word in BANNED:
            self.assertNotIn(word, text.lower())

    def test_state_keeps_last_30_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.json"
            state = {"sent": {f"2026-10-{d:02d}": ["nifty-2"] for d in range(1, 32)}}
            fa.save_state(path, state, TODAY)
            self.assertEqual(len(fa.load_state(path)["sent"]), 30)


if __name__ == "__main__":
    unittest.main()
