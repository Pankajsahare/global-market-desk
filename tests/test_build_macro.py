"""build_macro.py साठी offline tests (network लागत नाही)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_macro  # noqa: E402

NOW = datetime(2026, 11, 8, 2, 0, tzinfo=timezone.utc)
CONFIG = {"repo_rate": {"value": 5.5, "as_of": "2026-10-07", "source": "RBI"}, "cpi_months": 24, "forex_weeks": 52}

WSS_PAGE = """<html><body><table><tr><td>Foreign Exchange Reserves*</td></tr>
<tr><td>Item</td><td>As on October 30, 2026</td><td>Variation over</td></tr>
<tr><td>1 Total Reserves</td><td>6,808,728</td><td>717,056</td><td>-24,777</td><td>-2,691</td></tr>
</table></body></html>"""


def cpi_row(year, month, inflation, sector="Combined", division="CPI (General)"):
    return {"year": str(year), "month": month, "state": "All India", "sector": sector,
            "division": division, "inflation": inflation}


def fake_get(fail=()):
    """URL नुसार ठरलेलं उत्तर देणारा fetch."""
    def get(url, params=None):
        params = params or {}
        if "cpi" in url:
            if "cpi" in fail:
                raise OSError("down")
            if params.get("year") == "2026":
                rows = [cpi_row(2026, "September", "5.54"), cpi_row(2026, "September", "6.08", sector="Rural"),
                        cpi_row(2026, "August", "5.10"), cpi_row(2026, "September", "7.36", division="Food and beverages")]
                return json.dumps({"data": rows, "meta_data": {"totalPages": 1}})
            return json.dumps({"data": [], "msg": "No Data Found"})
        if "nas" in url:
            if "gdp" in fail:
                raise OSError("down")
            rows = [{"year": "2026-27", "quarter": "Q1", "constant_price": "7.8"},
                    {"year": "2025-26", "quarter": "Q4", "constant_price": "8.6"},
                    {"year": "2025-26", "quarter": "Q1", "constant_price": "6.9"}]
            return json.dumps({"data": rows})
        if "Wss" in url:
            if "forex" in fail:
                raise OSError("down")
            if not params:
                return 'href="BS_viewWssExtract.aspx?SelectedDate=11/06/2026"'
            return WSS_PAGE if params.get("SelectedDate") == "11/06/2026" else "<html>none</html>"
        raise AssertionError(url)
    return get


class BuildTests(unittest.TestCase):
    def test_full_snapshot(self):
        out, failed = build_macro.build(fake_get(), CONFIG, {}, NOW)
        self.assertEqual(failed, [])
        self.assertEqual(out["repo"]["value"], 5.5)
        self.assertEqual((out["cpi"]["value"], out["cpi"]["period"]), (5.54, "2026-09"))
        self.assertEqual(out["cpi"]["history"], [["2026-08", 5.1], ["2026-09", 5.54]])
        self.assertEqual((out["gdp"]["value"], out["gdp"]["period"]), (7.8, "Q1 FY26-27"))
        self.assertEqual(out["gdp"]["history"][0][0], "Q1 FY25-26")
        self.assertEqual((out["forex"]["value"], out["forex"]["as_of"], out["forex"]["change_week"]),
                         (717.06, "2026-10-30", -2.69))

    def test_failed_source_keeps_previous_as_stale(self):
        previous = {"gdp": {"value": 7.5, "period": "Q4 FY25-26", "history": []}}
        out, failed = build_macro.build(fake_get(fail=("gdp",)), CONFIG, previous, NOW)
        self.assertEqual(failed, ["gdp"])
        self.assertTrue(out["gdp"]["stale"])
        self.assertEqual(out["gdp"]["value"], 7.5)

    def test_out_of_range_repo_is_rejected(self):
        bad = {**CONFIG, "repo_rate": {"value": 55, "as_of": "2026-10-07"}}
        with self.assertRaises(ValueError):
            build_macro.build(fake_get(), bad, {}, NOW)

    def test_forex_keeps_history_and_adds_new_week(self):
        previous = {"history": [[f"2026-{m:02d}-01", 700.0] for m in range(1, 10)] * 1}
        previous["history"] += [[f"2025-{m:02d}-0{d}", 690.0] for m in range(1, 13) for d in (1, 8)]
        forex = build_macro.fetch_forex(fake_get(), previous, NOW, 52)
        self.assertEqual(forex["history"][-1], ["2026-10-30", 717.06])
        self.assertLessEqual(len(forex["history"]), 52)


class ParseWssTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(build_macro.parse_wss(WSS_PAGE), ("2026-10-30", 717.06, -2.69))

    def test_missing_table(self):
        self.assertIsNone(build_macro.parse_wss("<html>maintenance</html>"))


if __name__ == "__main__":
    unittest.main()
