"""seo-monitor/seo_audit.py tests — network शिवाय HTML parsing आणि issue नियम."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "seo-monitor"))

from seo_audit import analyse_html, build_message, compare, find_issues, weekly_sample  # noqa: E402

URL = "https://www.advisor4u.in/loans/"
GOOD = """<html><head><title>Loan Against Mutual Funds &amp; Home Loans | Sahare Wealth</title>
<meta name="description" content="Get liquidity with loans against mutual funds, shares and bonds without selling investments, plus home and business loans.">
<meta name="robots" content="index, follow"><link rel="canonical" href="https://www.advisor4u.in/loans/">
<script type="application/ld+json">{"@type":"Service"}</script></head>
<body><svg><title>Google Reviews</title></svg><h1>Loans made simple</h1><img src="a.png" alt="Loan"></body></html>"""


class AnalyseTests(unittest.TestCase):
    def test_clean_page_has_no_issues(self):
        info = analyse_html(GOOD)
        self.assertEqual(info["titles"], 1)  # SVG मधला title मोजला जात नाही
        self.assertEqual(info["title"], "Loan Against Mutual Funds & Home Loans | Sahare Wealth")
        self.assertEqual(find_issues(URL, 200, URL, 0.8, info), [])

    def test_duplicate_tags_from_pasted_document(self):
        html = GOOD.replace("<h1>", '<!doctype html><title>Other</title><meta name="description" content="x"><h1>')
        issues = find_issues(URL, 200, URL, 0.5, analyse_html(html))
        self.assertIn("duplicate_title_tag", issues)
        self.assertIn("duplicate_description_tag", issues)

    def test_bad_jsonld_alt_and_h1(self):
        html = GOOD.replace('{"@type":"Service"}', "").replace('alt="Loan"', 'alt=" "').replace("<h1>Loans made simple</h1>", "")
        issues = find_issues(URL, 200, URL, 0.5, analyse_html(html))
        for code in ("invalid_jsonld", "img_missing_alt", "missing_h1"):
            self.assertIn(code, issues)

    def test_status_redirect_noindex_slow_suspicious(self):
        self.assertEqual(find_issues(URL, 404, URL, 0.1, analyse_html("")), ["http_404"])
        info = analyse_html(GOOD.replace("index, follow", "noindex, follow"))
        old = "https://www.advisor4u.in/portfolio_old/"
        issues = find_issues(old, 200, URL, 4.2, info)
        for code in ("redirected", "noindex_in_sitemap", "slow", "suspicious_url"):
            self.assertIn(code, issues)

    def test_noindex_page_skips_on_page_checks(self):
        html = GOOD.replace("index, follow", "noindex, follow").replace("<h1>Loans made simple</h1>", "")
        self.assertEqual(find_issues(URL, 200, URL, 0.5, analyse_html(html)), ["noindex_in_sitemap"])


class CompareTests(unittest.TestCase):
    def test_new_and_fixed(self):
        rows = [{"url": "a", "issues": "missing_h1 slow"}, {"url": "b", "issues": ""}]
        state, new, fixed = compare(rows, {"a": ["slow"], "b": ["missing_h1"]})
        self.assertEqual(state, {"a": ["missing_h1", "slow"]})
        self.assertEqual(new, [("a", "missing_h1")])
        self.assertEqual(fixed, 1)
        msg = build_message(rows, new, fixed, "2026-11-15")
        self.assertIn("new issues: 1 | fixed: 1", msg)
        self.assertIn("missing_h1: a", msg)

    def test_weekly_sample_rotates(self):
        urls = [str(i) for i in range(250)]
        self.assertEqual(weekly_sample(urls, 100, 0)[0], "0")
        self.assertEqual(weekly_sample(urls, 100, 1)[0], "100")
        self.assertEqual(len(weekly_sample(urls, 100, 2)), 50)
        self.assertEqual(weekly_sample(urls[:10], 100, 5), urls[:10])


if __name__ == "__main__":
    unittest.main()
