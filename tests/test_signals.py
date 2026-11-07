"""signals.py, alert.py, morning_brief.py tests + JS widget शी parity (node असल्यास)."""
import json
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import alert  # noqa: E402
import morning_brief  # noqa: E402
import signals  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures_market.json").read_text(encoding="utf-8"))


class SignalTests(unittest.TestCase):
    def test_cue_on_real_snapshot(self):
        mapping, _ = signals.index_items(FIXTURE)
        cue = signals.compute_cue(mapping)
        self.assertAlmostEqual(cue["coverage"], 1.0)
        self.assertIn(cue["label"], {"Positive", "Mildly Positive", "Flat", "Mildly Negative", "Negative"})

    def test_cue_missing_data_renormalises(self):
        cue = signals.compute_cue({"INR=X": {"symbol": "INR=X", "r1d": -1.0}})
        self.assertAlmostEqual(cue["coverage"], 0.10)
        self.assertAlmostEqual(cue["score"], 1.0)  # rupee मजबूत → +1
        self.assertEqual(cue["label"], "Positive")

    def test_mood_high_vix_is_negative(self):
        mood = signals.compute_mood({"^VIX": {"last": 30}}, [])
        self.assertEqual((mood["score"], mood["label"]), (35, "Risk-Off"))


class AlertTests(unittest.TestCase):
    def test_third_failure_alerts_once(self):
        self.assertEqual(alert.decide("failure", ["failure", "failure", "success"]), "alert")
        self.assertIsNone(alert.decide("failure", ["failure", "failure", "failure"]))  # 4th → spam नाही
        self.assertIsNone(alert.decide("failure", ["failure", "success"]))

    def test_recovery(self):
        self.assertEqual(alert.decide("success", ["failure"] * 3), "recovered")
        self.assertIsNone(alert.decide("success", ["failure", "failure"]))


class BriefTests(unittest.TestCase):
    def test_message_contents(self):
        now = datetime.fromisoformat(FIXTURE["updated"]).astimezone(morning_brief.IST)
        msg = morning_brief.build_message(FIXTURE, now=now)
        self.assertIn("India open cue:", msg)
        self.assertIn("Risk mood:", msg)
        self.assertIn("not investment advice", msg)
        self.assertNotIn("Data is", msg)

    def test_stale_warning(self):
        now = datetime.fromisoformat(FIXTURE["updated"]).astimezone(morning_brief.IST) + timedelta(hours=3)
        self.assertIn("⚠️ Data is", morning_brief.build_message(FIXTURE, now=now))


@unittest.skipUnless(shutil.which("node"), "node not installed")
class JsParityTests(unittest.TestCase):
    """Widget मधले JS rules आणि Python rules एकच निकाल देतात का."""

    def test_same_results(self):
        src = (ROOT / "public" / "widget" / "gmd.js").read_text(encoding="utf-8")
        js = src.split("// ---------- start ----------", 1)[0]
        js = js.replace("(function () {", "", 1)
        harness = js + """
        var data = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
        var all = [].concat.apply([], Object.values(data.groups)); var map = {};
        all.forEach(function (i) { map[i.symbol] = i; });
        var cue = computeCue(map), mood = computeMood(map, data.groups.global);
        console.log(JSON.stringify({cue: cue.score, cueLabel: cue.label, mood: mood.score, moodLabel: mood.label,
          reasons: mood.reasons.map(function (r) { return [r.points, r.text]; })}));
        """
        out = subprocess.run(["node", "-e", harness, str(ROOT / "tests" / "fixtures_market.json")],
                             capture_output=True, text=True, check=True).stdout
        js_result = json.loads(out)
        mapping, globals_ = signals.index_items(FIXTURE)
        cue, mood = signals.compute_cue(mapping), signals.compute_mood(mapping, globals_)
        self.assertAlmostEqual(js_result["cue"], cue["score"], places=9)
        self.assertEqual(js_result["cueLabel"], cue["label"])
        self.assertEqual(js_result["mood"], mood["score"])
        self.assertEqual(js_result["moodLabel"], mood["label"])
        self.assertEqual([tuple(r) for r in js_result["reasons"]], mood["reasons"])


if __name__ == "__main__":
    unittest.main()
