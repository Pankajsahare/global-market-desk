"""S3 NSE fallback tests (network नाही)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_data  # noqa: E402
import nse_source as ns  # noqa: E402

ROW = {"index": "NIFTY 50", "last": 24420.5, "previousClose": 25030.35, "oneWeekAgoVal": "23,052.10",
       "oneMonthAgo": 22600.0, "perChange365d": -1.2, "_timestamp": "09-Nov-2026 13:15:00"}
CFG = {"symbol": "^NSEI", "name": "NIFTY 50", "region": "India", "nse": "NIFTY 50"}


class NseItemTests(unittest.TestCase):
    def test_parse_row(self):
        item = ns.nse_item(CFG, ROW, {"r3m": 1.5, "spark": [1, 2]})
        self.assertEqual(item["r1d"], round((24420.5 - 25030.35) / 25030.35 * 100, 2))
        self.assertEqual(item["r1w"], round((24420.5 - 23052.10) / 23052.10 * 100, 2))  # comma असलेला string
        self.assertEqual(item["r1m"], round((24420.5 - 22600) / 22600 * 100, 2))       # दुसरं key नाव
        self.assertEqual(item["r1y"], -1.2)
        self.assertEqual((item["r3m"], item["spark"]), (1.5, [1, 2]))                  # मागचं मूल्य
        self.assertEqual((item["asof"], item["region"], item["sourceSymbol"]), ("2026-11-09", "India", "nse:NIFTY 50"))

    def test_missing_price_returns_none(self):
        self.assertIsNone(ns.nse_item(CFG, {"index": "NIFTY 50"}))

    def test_lazy_single_fetch(self):
        calls = []
        client = ns.NseIndices(lambda: calls.append(1) or {"NIFTY 50": ROW})
        client.get("nifty 50")
        client.get("NIFTY BANK")
        self.assertEqual(len(calls), 1)


class BuildFallbackTests(unittest.TestCase):
    def test_nse_used_only_when_yahoo_fails(self):
        cfg = {"groups": {"global": [CFG]}}
        data, success, _ = build_data.build_dataset(cfg, {}, fetcher=lambda s: None, pause=0,
                                                    nse_lookup=lambda n: ROW if n == "NIFTY 50" else None)
        self.assertEqual(success, 1)
        self.assertEqual(data["groups"]["global"][0]["sourceSymbol"], "nse:NIFTY 50")

        calls = []
        from test_build_data import make_result  # noqa: E402
        from datetime import date
        good = make_result(date(2026, 1, 1), [1.0, 2.0])
        build_data.build_dataset(cfg, {}, fetcher=lambda s: good, pause=0, nse_lookup=lambda n: calls.append(n))
        self.assertEqual(calls, [])  # Yahoo चाललं → NSE ला हात नाही

    def test_no_nse_mapping_means_no_call(self):
        calls = []
        build_data.build_dataset({"groups": {"g": [{"symbol": "^GSPC", "name": "S&P 500"}]}}, {},
                                 fetcher=lambda s: None, pause=0, nse_lookup=lambda n: calls.append(n))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
