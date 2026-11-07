"""build_data.py साठी offline tests (network लागत नाही)."""
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_data  # noqa: E402


def make_result(start: date, closes, gmtoffset=0, market_time=1762500000):
    """Yahoo सारखा fake chart result बनवा — दररोज एक bar."""
    timestamps = []
    for i, _ in enumerate(closes):
        day = start + timedelta(days=i)
        timestamps.append(int(datetime(day.year, day.month, day.day, 10, tzinfo=timezone.utc).timestamp()))
    return {
        "meta": {"gmtoffset": gmtoffset, "regularMarketTime": market_time},
        "timestamp": timestamps,
        "indicators": {"quote": [{"close": list(closes)}]},
    }


class ParseSeriesTests(unittest.TestCase):
    def test_skips_null_closes(self):
        result = make_result(date(2026, 1, 1), [100.0, None, 102.0])
        series = build_data.parse_series(result)
        self.assertEqual([v for _, v in series], [100.0, 102.0])

    def test_duplicate_dates_keep_last(self):
        result = make_result(date(2026, 1, 1), [100.0, 101.0])
        result["timestamp"][1] = result["timestamp"][0] + 3600  # त्याच दिवशी दुसरा bar
        series = build_data.parse_series(result)
        self.assertEqual(series, [("2026-01-01", 101.0)])


class BuildItemTests(unittest.TestCase):
    def setUp(self):
        # 400 दिवस, 100 → 499 (रोज +1)
        self.closes = [100.0 + i for i in range(400)]
        self.result = make_result(date(2025, 1, 1), self.closes)
        self.cfg = {"symbol": "^TEST", "name": "Test Index", "region": "India"}

    def test_returns(self):
        item = build_data.build_item(self.cfg, self.result)
        last = self.closes[-1]
        self.assertEqual(item["last"], last)
        self.assertEqual(item["r1d"], round((last - self.closes[-2]) / self.closes[-2] * 100, 2))
        self.assertEqual(item["r1w"], round((last - self.closes[-8]) / self.closes[-8] * 100, 2))
        self.assertEqual(item["r1y"], round((last - self.closes[-366]) / self.closes[-366] * 100, 2))
        self.assertEqual(item["d1w"], 7.0)
        self.assertEqual(item["region"], "India")
        self.assertEqual(len(item["spark"]), build_data.SPARK_POINTS)
        self.assertFalse(item["stale"])

    def test_short_history_gives_none_for_long_windows(self):
        result = make_result(date(2026, 1, 1), [10.0, 11.0, 12.0])
        item = build_data.build_item(self.cfg, result)
        self.assertIsNone(item["r1y"])
        self.assertIsNotNone(item["r1d"])

    def test_single_point_returns_none(self):
        self.assertIsNone(build_data.build_item(self.cfg, make_result(date(2026, 1, 1), [10.0])))


class BuildDatasetTests(unittest.TestCase):
    def test_failed_symbol_uses_previous_as_stale(self):
        config = {"groups": {"g": [{"symbol": "OK", "name": "Ok"}, {"symbol": "BAD", "name": "Bad"}]}}
        good = make_result(date(2026, 1, 1), [1.0, 2.0])
        previous = {"BAD": {"symbol": "BAD", "name": "Bad", "last": 5.0, "stale": False}}

        def fetcher(symbol):
            return good if symbol == "OK" else None

        data, success, total = build_data.build_dataset(config, previous, fetcher=fetcher, pause=0)
        self.assertEqual((success, total), (1, 2))
        items = {i["symbol"]: i for i in data["groups"]["g"]}
        self.assertTrue(items["BAD"]["stale"])
        self.assertFalse(items["OK"]["stale"])

    def test_fallback_symbol_used_when_primary_fails(self):
        config = {"groups": {"funds": [{"symbol": "MAIN", "name": "Main", "category": "Mid Cap",
                                        "fallbacks": [{"symbol": "ALT", "name": "Alt Index"}]}]}}
        good = make_result(date(2026, 1, 1), [1.0, 2.0])
        data, success, _ = build_data.build_dataset(
            config, {}, fetcher=lambda s: good if s == "ALT" else None, pause=0)
        item = data["groups"]["funds"][0]
        self.assertEqual(success, 1)
        self.assertEqual((item["symbol"], item["sourceSymbol"], item["name"]), ("MAIN", "ALT", "Alt Index"))
        self.assertEqual(item["category"], "Mid Cap")

    def test_short_history_primary_replaced_by_longer_fallback(self):
        config = {"groups": {"funds": [{"symbol": "MAIN", "name": "Main", "minPoints": 250,
                                        "fallbacks": [{"symbol": "ALT1", "name": "Alt1"},
                                                      {"symbol": "ALT2", "name": "Alt2"}]}]}}
        results = {
            "MAIN": make_result(date(2026, 1, 1), [1.0 + i for i in range(13)]),
            "ALT1": make_result(date(2025, 1, 1), [1.0 + i for i in range(100)]),
            "ALT2": make_result(date(2025, 1, 1), [1.0 + i for i in range(60)]),
        }
        data, _, _ = build_data.build_dataset(config, {}, fetcher=results.get, pause=0)
        self.assertEqual(data["groups"]["funds"][0]["sourceSymbol"], "ALT1")  # सर्वात लांब history

    def test_main_refuses_to_write_when_most_fail(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            out = Path(tmp) / "out" / "m.json"
            cfg.write_text(json.dumps({"groups": {"g": [{"symbol": "X", "name": "X"}]}}), encoding="utf-8")
            original = build_data.fetch_chart
            build_data.fetch_chart = lambda s: None
            try:
                # build_dataset चा default fetcher import वेळी bind होतो — म्हणून थेट patch
                original_build = build_data.build_dataset
                build_data.build_dataset = lambda c, p, **kw: original_build(c, p, fetcher=lambda s: None, pause=0)
                code = build_data.main(["--config", str(cfg), "--out", str(out)])
            finally:
                build_data.fetch_chart = original
                build_data.build_dataset = original_build
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()


class IndexProxyTests(unittest.TestCase):
    """S6: invest-core index closes."""

    def setUp(self):
        start = date(2025, 6, 1)
        self.series = {"Nifty Midcap 150": [((start + timedelta(days=i)).isoformat(), 100.0 + i) for i in range(400)]}
        self.cfg = {"groups": {"funds": [{"symbol": "MID", "name": "Mid ETF", "category": "Mid Cap",
                                          "indexHistory": "Nifty Midcap 150", "indexName": "NIFTY Midcap 150",
                                          "minPoints": 250}]}}

    def test_fresh_index_used_without_yahoo(self):
        calls = []
        data, success, _ = build_data.build_dataset(
            self.cfg, {}, fetcher=lambda s: calls.append(s), pause=0,
            index_series=self.series, today=date(2026, 7, 8))
        item = data["groups"]["funds"][0]
        self.assertEqual((success, calls), (1, []))
        self.assertEqual((item["name"], item["sourceSymbol"], item["category"]),
                         ("NIFTY Midcap 150", "invest-core:Nifty Midcap 150", "Mid Cap"))
        self.assertIsNotNone(item["r1y"])

    def test_stale_index_falls_back_to_yahoo(self):
        calls = []
        build_data.build_dataset(self.cfg, {}, fetcher=lambda s: calls.append(s), pause=0,
                                 index_series=self.series, today=date(2026, 8, 30))
        self.assertEqual(calls, ["MID"])

    def test_load_index_proxies_ignores_bad_rows(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps({"series": {"X": [["2026-01-02", 2.0], ["2026-01-01", 1.0], ["2026-01-03", None]]}}))
            self.assertEqual(build_data.load_index_proxies(path), {"X": [("2026-01-01", 1.0), ("2026-01-02", 2.0)]})
            self.assertEqual(build_data.load_index_proxies(Path(tmp) / "missing.json"), {})
