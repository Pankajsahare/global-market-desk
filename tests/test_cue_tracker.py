"""cue_tracker.py tests (offline)."""
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cue_tracker as ct  # noqa: E402

IST = ct.IST


def bars_result(rows):
    """rows: [(date, open, close)] → Yahoo सारखा result."""
    ts = [int(datetime(d.year, d.month, d.day, 4, tzinfo=timezone.utc).timestamp()) for d, _, _ in rows]
    return {"meta": {"gmtoffset": 19800}, "timestamp": ts,
            "indicators": {"quote": [{"open": [o for _, o, _ in rows], "close": [c for _, _, c in rows]}]}}


def at(day, hour):
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=IST)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "log.json"
        self.cue_up = {"score": 0.4, "label": "Mildly Positive"}
        self.mood = {"score": 55, "label": "Neutral"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_weekend_not_recorded(self):
        self.assertFalse(ct.record(self.log, self.cue_up, self.mood, at(date(2026, 11, 7), 8)))  # Saturday

    def test_record_then_hit(self):
        mon = date(2026, 11, 9)
        ct.record(self.log, self.cue_up, self.mood, at(mon, 8))
        result = bars_result([(date(2026, 11, 6), 100, 100.0), (mon, 100.5, 101)])  # gap +0.5%
        self.assertEqual(ct.evaluate(self.log, lambda s: result, at(mon, 16)), 1)
        entry = ct.load_log(self.log)["entries"][0]
        self.assertEqual((entry["status"], entry["actualDir"], entry["hit"]), ("done", "up", True))
        self.assertEqual(ct.hit_rate(ct.load_log(self.log)), (1, 1))

    def test_miss_and_flat_band(self):
        mon = date(2026, 11, 9)
        ct.record(self.log, self.cue_up, self.mood, at(mon, 8))
        result = bars_result([(date(2026, 11, 6), 100, 100.0), (mon, 100.1, 99)])  # gap +0.1% = flat
        ct.evaluate(self.log, lambda s: result, at(mon, 16))
        entry = ct.load_log(self.log)["entries"][0]
        self.assertEqual((entry["actualDir"], entry["hit"]), ("flat", False))

    def test_holiday_and_pending(self):
        tue = date(2026, 11, 10)
        ct.record(self.log, self.cue_up, self.mood, at(tue, 8))
        result = bars_result([(date(2026, 11, 6), 100, 100.0), (date(2026, 11, 9), 100, 100.0)])
        self.assertEqual(ct.evaluate(self.log, lambda s: result, at(tue, 12)), 0)   # अजून लवकर → pending
        self.assertEqual(ct.evaluate(self.log, lambda s: result, at(tue, 16)), 1)
        self.assertEqual(ct.load_log(self.log)["entries"][0]["status"], "holiday")

    def test_done_entry_not_overwritten(self):
        mon = date(2026, 11, 9)
        ct.record(self.log, self.cue_up, self.mood, at(mon, 8))
        ct.evaluate(self.log, lambda s: bars_result([(date(2026, 11, 6), 1, 100.0), (mon, 101, 101)]), at(mon, 16))
        self.assertFalse(ct.record(self.log, {"score": -1, "label": "Negative"}, self.mood, at(mon, 17)))

    def test_suspect_open(self):
        mon = date(2026, 11, 9)
        ct.record(self.log, self.cue_up, self.mood, at(mon, 8))
        ct.evaluate(self.log, lambda s: bars_result([(date(2026, 11, 6), 1, 100.0), (mon, 100.0, 101)]), at(mon, 16))
        self.assertEqual(ct.load_log(self.log)["entries"][0]["status"], "suspect")
        self.assertIsNone(ct.hit_rate(ct.load_log(self.log)))


if __name__ == "__main__":
    unittest.main()
