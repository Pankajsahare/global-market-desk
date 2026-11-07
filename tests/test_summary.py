"""summary.py tests — descriptive वाक्यं, सल्ल्याचे शब्द नाहीत."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from summary import build_summary  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures_market.json").read_text(encoding="utf-8"))
BANNED = ("buy", "sell", "should", "recommend", "expect", "will ", "target", "advice")


class SummaryTests(unittest.TestCase):
    def test_real_snapshot(self):
        lines = build_summary(FIXTURE["groups"])
        self.assertTrue(3 <= len(lines) <= 6)
        self.assertTrue(lines[0].startswith("NIFTY 50 rose 2.01%"))
        self.assertIn("Asian markets fell sharply, led by KOSPI (-6.02%).", lines)

    def test_no_advice_words(self):
        text = " ".join(build_summary(FIXTURE["groups"])).lower()
        for word in BANNED:
            self.assertNotIn(word, text)

    def test_stale_items_ignored(self):
        groups = {"global": [{"symbol": "^NSEI", "name": "NIFTY 50", "last": 1, "r1d": 1.0, "stale": True}]}
        self.assertEqual(build_summary(groups), [])

    def test_mixed_region(self):
        groups = {"global": [
            {"symbol": "a", "name": "A", "region": "US", "last": 1, "r1d": 0.4},
            {"symbol": "b", "name": "B", "region": "US", "last": 1, "r1d": -0.3},
            {"symbol": "c", "name": "C", "region": "US", "last": 1, "r1d": 0.1}]}
        self.assertEqual(build_summary(groups), ["Wall Street was mixed: A +0.40%, B -0.30%, C +0.10%."])


if __name__ == "__main__":
    unittest.main()
