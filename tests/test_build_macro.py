"""build_macro.py साठी offline tests (network लागत नाही)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_macro  # noqa: E402

NOW = datetime(2026, 11, 8, 2, 0, tzinfo=timezone.utc)
CONFIG = {"repo_rate": {"value": 5.5, "as_of": "2026-10-07", "source": "RBI"}, "cpi_months": 24, "forex_weeks": 52,
          "fd_rate": {"value": 6.4, "label": "SBI FD, 2 to 3 years", "as_of": "2026-11-08"}}

WSS_PAGE = """<html><body><table><tr><td>Foreign Exchange Reserves*</td></tr>
<tr><td>Item</td><td>As on October 30, 2026</td><td>Variation over</td></tr>
<tr><td>1 Total Reserves</td><td>6,808,728</td><td>717,056</td><td>-24,777</td><td>-2,691</td></tr>
</table></body></html>"""


HOME_PAGE = """<div>Market Trends Government Securities Market 6.20% GS 2029 : 6.9581% # 6.53% GS 2031 : 7.0231% #
6.94% GS 2036 : 7.1620% # 7.06% GS 2041 : 7.3432% # 91 day T-bills : 5.8970%* # as on November 05, 2026 Capital Market</div>"""


def cpi_row(year, month, inflation, sector="Combined", division="CPI (General)"):
    return {"year": str(year), "month": month, "state": "All India", "sector": sector,
            "division": division, "inflation": inflation}


def fake_get(fail=()):
    """URL नुसार ठरलेलं उत्तर देणारा fetch."""
    def get(url, params=None):
        params = params or {}
        if "getCPIIndex" in url:
            if params.get("year") == "2025":
                rows = [{"year": "2025", "month": "December", "sector": "Combined", "group": "General Index",
                         "subgroup": "General", "inflation": "1.33"},
                        {"year": "2025", "month": "December", "sector": "Combined", "group": "Miscellaneous",
                         "subgroup": "Education", "inflation": "3.37"},
                        {"year": "2025", "month": "November", "sector": "Combined", "group": "General Index",
                         "subgroup": "General", "inflation": "0.71"}]
                return json.dumps({"data": rows, "meta_data": {"totalPages": 1}})
            return json.dumps({"data": []})
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
        if "home.aspx" in url:
            if "gsec" in fail:
                raise OSError("down")
            return HOME_PAGE
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
        out, failed = build_macro.build(fake_get(), CONFIG, {}, NOW, lambda _: None)
        self.assertEqual(failed, [])
        self.assertEqual(out["repo"]["value"], 5.5)
        self.assertEqual((out["cpi"]["value"], out["cpi"]["period"]), (5.54, "2026-09"))
        self.assertEqual(out["cpi"]["history"],
                         [["2025-11", 0.71], ["2025-12", 1.33], ["2026-08", 5.1], ["2026-09", 5.54]])
        self.assertEqual(out["cpi"]["base_2012_until"], "2025-12")
        self.assertEqual(out["real_return"]["value"], 0.86)
        self.assertEqual((out["gsec"]["value"], out["gsec"]["bond"]), (7.16, "6.94% GS 2036"))
        self.assertEqual((out["gdp"]["value"], out["gdp"]["period"]), (7.8, "Q1 FY26-27"))
        self.assertEqual(out["gdp"]["history"][0][0], "Q1 FY25-26")
        self.assertEqual((out["forex"]["value"], out["forex"]["as_of"], out["forex"]["change_week"]),
                         (717.06, "2026-10-30", -2.69))

    def test_failed_source_keeps_previous_as_stale(self):
        previous = {"gdp": {"value": 7.5, "period": "Q4 FY25-26", "history": []}}
        out, failed = build_macro.build(fake_get(fail=("gdp",)), CONFIG, previous, NOW, lambda _: None)
        self.assertEqual(failed, ["gdp"])
        self.assertTrue(out["gdp"]["stale"])
        self.assertEqual(out["gdp"]["value"], 7.5)

    def test_out_of_range_repo_is_rejected(self):
        bad = {**CONFIG, "repo_rate": {"value": 55, "as_of": "2026-10-07"}}
        with self.assertRaises(ValueError):
            build_macro.build(fake_get(), bad, {}, NOW, lambda _: None)

    def test_forex_keeps_history_and_adds_new_week(self):
        previous = {"history": [[f"2026-{m:02d}-01", 700.0] for m in range(1, 10)] * 1}
        previous["history"] += [[f"2025-{m:02d}-0{d}", 690.0] for m in range(1, 13) for d in (1, 8)]
        forex = build_macro.fetch_forex(fake_get(), previous, NOW, 52, lambda _: None)
        self.assertEqual(forex["history"][-1], ["2026-10-30", 717.06])
        self.assertLessEqual(len(forex["history"]), 52)


class ExtraTests(unittest.TestCase):
    def test_gsec_picks_ten_year_bond(self):
        self.assertEqual(build_macro.parse_gsec(HOME_PAGE, 2026), ("2026-11-05", "6.94% GS 2036", 7.162))

    def test_repo_line_follows_changes(self):
        history = [["2025-06-06", 5.5], ["2025-12-05", 5.25], ["2026-10-07", 5.5]]
        self.assertEqual([build_macro.repo_on(history, p) for p in ("2025-05", "2025-11", "2025-12", "2026-10")],
                         [None, 5.5, 5.25, 5.5])

    def test_cpi_release_alert_with_draft(self):
        prev = {"cpi": {"value": 4.83, "period": "2026-08"}}
        out = {"cpi": {"value": 5.54, "period": "2026-09"}, "real_return": {"fd": 6.4, "value": 0.86}}
        msgs = build_macro.release_alerts(prev, out)
        self.assertEqual(len(msgs), 1)
        self.assertIn("September 2026", msgs[0])
        self.assertIn("+0.86%", msgs[0])
        self.assertEqual(build_macro.release_alerts(out, out), [])

    def test_mpc_reminder_weekly_after_three_days(self):
        cfg = {"repo_rate": {"as_of": "2026-10-07"}, "mpc_decisions": ["2026-10-07", "2026-12-04"]}
        on = lambda d: build_macro.reminders(cfg, datetime.fromisoformat(d))
        self.assertEqual(on("2026-12-06"), [])
        self.assertEqual(len(on("2026-12-07")), 1)
        self.assertEqual(on("2026-12-08"), [])
        self.assertEqual(len(on("2026-12-14")), 1)
        cfg["repo_rate"]["as_of"] = "2026-12-04"
        self.assertEqual(on("2026-12-07"), [])


class StaleTests(unittest.TestCase):
    def test_stale_cpi_alerts_weekly(self):
        out = {"cpi": {"period": "2026-09"}, "forex": {"as_of": "2026-10-30"}}
        on = lambda d: build_macro.stale_alerts(out, datetime.fromisoformat(d))
        self.assertEqual(on("2026-11-18"), [])                 # CPI 48 दिवस, forex 19 दिवस पण 16 + 7k नाही
        self.assertEqual(len(on("2026-11-19")), 1)             # CPI 50 दिवस
        self.assertIn("CPI", on("2026-11-19")[0])
        self.assertEqual(len(on("2026-11-15")), 1)             # forex 16 दिवस

    def test_gdp_reference_day(self):
        self.assertEqual(build_macro._reference_day("gdp", {"period": "Q1 FY26-27"}), "2026-06-30")
        self.assertEqual(build_macro._reference_day("gdp", {"period": "Q4 FY25-26"}), "2026-03-31")
        self.assertEqual(build_macro._reference_day("cpi", {"period": "2026-12"}), "2026-12-31")


class ParseWssTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(build_macro.parse_wss(WSS_PAGE), ("2026-10-30", 717.06, -2.69))

    def test_abbreviated_months(self):
        self.assertEqual(build_macro._wss_day("Jul. 03, 2026"), "2026-07-03")
        self.assertEqual(build_macro._wss_day("Sept. 4, 2026"), "2026-09-04")
        self.assertEqual(build_macro._wss_day("May 29, 2026"), "2026-05-29")

    def test_missing_table(self):
        self.assertIsNone(build_macro.parse_wss("<html>maintenance</html>"))


if __name__ == "__main__":
    unittest.main()
