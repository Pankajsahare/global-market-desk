"""advisor4u.in साप्ताहिक SEO तपासणी (standard library फक्त).

Sitemap मधली पानं उघडून प्रत्येकाचा HTTP status, redirect, response time आणि on-page SEO
(title, meta description, H1, canonical, robots, JSON-LD, image alt) तपासते.
अहवाल CSV मध्ये लिहिते, मागच्या आठवड्याशी तुलना करते आणि नवीन चुका private Telegram वर पाठवते.

वापर:
    python seo-monitor/seo_audit.py                 # फक्त अहवाल
    python seo-monitor/seo_audit.py --send          # अहवाल + Telegram summary
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

SITE = "https://www.advisor4u.in"
# पूर्ण तपासायचे sitemaps
FULL_SITEMAPS = ["/sitemap.xml", "/local-sitemap.xml"]
# मोठा sitemap (1,200+ bond पानं): दर आठवड्याला फक्त एक भाग (नमुना) तपासतो
SAMPLED_SITEMAPS = {"/bond-sitemap.xml": 100}
USER_AGENT = "Advisor4uSEOMonitor/1.0 (+https://www.advisor4u.in; weekly self-audit)"
DELAY_SECONDS = 1.0          # server वर भार येऊ नये म्हणून प्रत्येक पानानंतर विराम
TIMEOUT_SECONDS = 25
SLOW_SECONDS = 3.0
TITLE_MAX = 65
DESC_MIN, DESC_MAX = 70, 170
# नाव पाहूनच संशय येणारे URLs (जुनी / copy / test पानं)
SUSPICIOUS = re.compile(r"(_old|-old|-copy|copy-|-2/$|test|draft|sample|demo|reserch)", re.I)

REPORT_DIR = HERE / "reports"
CSV_PATH = REPORT_DIR / "latest.csv"
STATE_PATH = REPORT_DIR / "issues.json"

COLUMNS = ["url", "status", "final_url", "seconds", "titles", "title", "title_len",
           "descriptions", "description_len", "h1_count", "canonical", "robots",
           "jsonld_total", "jsonld_bad", "img_no_alt", "issues"]


class PageParser(HTMLParser):
    """एका पानातून SEO घटक गोळा करतो. SVG आतले <title> (icons) मोजत नाही."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.svg_depth = 0
        self.in_title = False
        self.in_jsonld = False
        self.titles: list[str] = []
        self.descriptions: list[str] = []
        self.robots = ""
        self.canonical = ""
        self.h1_count = 0
        self.img_no_alt = 0
        self.jsonld_blocks: list[str] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "svg":
            self.svg_depth += 1
        elif tag == "title" and self.svg_depth == 0:
            self.in_title, self._buf = True, []
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name == "description":
                self.descriptions.append(a.get("content", "").strip())
            elif name == "robots" and not self.robots:
                self.robots = a.get("content", "").strip().lower()
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and not self.canonical:
            self.canonical = a.get("href", "").strip()
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "img":
            # data: placeholders नसलेले, alt नसलेले किंवा रिकाम्या alt असलेले
            if "alt" not in a or not a["alt"].strip():
                if a.get("role", "") != "presentation" and a.get("aria-hidden", "") != "true":
                    self.img_no_alt += 1
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_jsonld, self._buf = True, []

    def handle_startendtag(self, tag, attrs):
        if tag != "svg":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "svg" and self.svg_depth:
            self.svg_depth -= 1
        elif tag == "title" and self.in_title:
            self.titles.append("".join(self._buf).strip())
            self.in_title = False
        elif tag == "script" and self.in_jsonld:
            self.jsonld_blocks.append("".join(self._buf))
            self.in_jsonld = False

    def handle_data(self, data):
        if self.in_title or self.in_jsonld:
            self._buf.append(data)


def analyse_html(html: str) -> dict:
    """HTML मधून SEO घटक काढा (network शिवाय — tests साठी वेगळे)."""
    p = PageParser()
    p.feed(html)
    bad = 0
    for block in p.jsonld_blocks:
        try:
            json.loads(block)
        except ValueError:
            bad += 1
    return {
        "titles": len(p.titles),
        "title": p.titles[0] if p.titles else "",
        "descriptions": len(p.descriptions),
        "description": p.descriptions[0] if p.descriptions else "",
        "h1_count": p.h1_count,
        "canonical": p.canonical,
        "robots": p.robots,
        "jsonld_total": len(p.jsonld_blocks),
        "jsonld_bad": bad,
        "img_no_alt": p.img_no_alt,
    }


def norm(url: str) -> str:
    return url.split("#")[0].split("?")[0].rstrip("/").lower()


def find_issues(url: str, status: int, final_url: str, seconds: float, info: dict) -> list[str]:
    """एका पानाच्या चुकांची यादी (छोटी code नावं)."""
    issues: list[str] = []
    if status != 200:
        issues.append(f"http_{status}")
        return issues
    if norm(final_url) != norm(url):
        issues.append("redirected")
    if "noindex" in info["robots"]:
        issues.append("noindex_in_sitemap")
    if info["titles"] == 0 or not info["title"]:
        issues.append("missing_title")
    elif info["titles"] > 1:
        issues.append("duplicate_title_tag")
    if len(info["title"]) > TITLE_MAX:
        issues.append("title_too_long")
    if info["descriptions"] == 0 or not info["description"]:
        issues.append("missing_description")
    elif info["descriptions"] > 1:
        issues.append("duplicate_description_tag")
    elif not DESC_MIN <= len(info["description"]) <= DESC_MAX:
        issues.append("description_length")
    if info["h1_count"] == 0:
        issues.append("missing_h1")
    if not info["canonical"]:
        issues.append("missing_canonical")
    elif norm(info["canonical"]) != norm(final_url):
        issues.append("canonical_mismatch")
    if info["jsonld_bad"]:
        issues.append("invalid_jsonld")
    if info["img_no_alt"]:
        issues.append("img_missing_alt")
    if seconds > SLOW_SECONDS:
        issues.append("slow")
    if SUSPICIOUS.search(url):
        issues.append("suspicious_url")
    return issues


def fetch(url: str) -> tuple[int, str, float, str]:
    """(status, final_url, seconds, html). 5xx/timeout आल्यास एकदा पुन्हा प्रयत्न."""
    for attempt in (1, 2):
        start = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return resp.status, resp.geturl(), time.monotonic() - start, body
        except urllib.error.HTTPError as exc:
            status, final = exc.code, exc.geturl() or url
        except (urllib.error.URLError, TimeoutError) as exc:
            status, final = 0, url
            print(f"WARN: {url}: {type(exc).__name__}", file=sys.stderr)
        if attempt == 1 and (status == 0 or status >= 500):
            time.sleep(5)
            continue
        return status, final, time.monotonic() - start, ""
    return 0, url, 0.0, ""


def sitemap_urls(path: str) -> list[str]:
    status, _, _, body = fetch(SITE + path)
    if status != 200:
        print(f"WARN: sitemap {path} returned {status}", file=sys.stderr)
        return []
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)


def weekly_sample(urls: list[str], size: int, week: int) -> list[str]:
    """दर आठवड्याला वेगळा सलग भाग — काही आठवड्यांत संपूर्ण यादी कव्हर होते."""
    if len(urls) <= size:
        return urls
    chunks = (len(urls) + size - 1) // size
    start = (week % chunks) * size
    return urls[start:start + size]


def collect_urls(week: int) -> list[str]:
    seen: dict[str, None] = {}
    for path in FULL_SITEMAPS:
        for u in sitemap_urls(path):
            seen.setdefault(u, None)
    for path, size in SAMPLED_SITEMAPS.items():
        for u in weekly_sample(sitemap_urls(path), size, week):
            seen.setdefault(u, None)
    return list(seen)


def audit(urls: list[str]) -> list[dict]:
    rows = []
    for i, url in enumerate(urls, 1):
        status, final, seconds, html = fetch(url)
        info = analyse_html(html) if html else analyse_html("")
        issues = find_issues(url, status, final, seconds, info)
        rows.append({
            "url": url, "status": status, "final_url": final, "seconds": round(seconds, 2),
            "titles": info["titles"], "title": info["title"], "title_len": len(info["title"]),
            "descriptions": info["descriptions"], "description_len": len(info["description"]),
            "h1_count": info["h1_count"], "canonical": info["canonical"], "robots": info["robots"],
            "jsonld_total": info["jsonld_total"], "jsonld_bad": info["jsonld_bad"],
            "img_no_alt": info["img_no_alt"], "issues": " ".join(issues),
        })
        if i % 25 == 0:
            print(f"checked {i}/{len(urls)}")
        time.sleep(DELAY_SECONDS)
    return rows


def compare(rows: list[dict], previous: dict) -> tuple[dict, list[tuple[str, str]], int]:
    """(नवीन state, नवीन चुका [(url, issue)], दुरुस्त झालेल्या चुकांची संख्या)."""
    current = {r["url"]: sorted(r["issues"].split()) for r in rows if r["issues"]}
    new: list[tuple[str, str]] = []
    for url, issues in current.items():
        old = set(previous.get(url, []))
        new.extend((url, i) for i in issues if i not in old)
    checked = {r["url"] for r in rows}
    fixed = sum(len(set(v) - set(current.get(u, []))) for u, v in previous.items() if u in checked)
    return current, new, fixed


def build_message(rows: list[dict], new: list[tuple[str, str]], fixed: int, today: str) -> str:
    counts: dict[str, int] = {}
    for r in rows:
        for i in r["issues"].split():
            counts[i] = counts.get(i, 0) + 1
    ok = sum(1 for r in rows if not r["issues"])
    lines = [f"advisor4u.in SEO audit — {today}",
             f"Pages checked: {len(rows)} | clean: {ok} | new issues: {len(new)} | fixed: {fixed}"]
    if counts:
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        lines.append("Issue counts: " + ", ".join(f"{k} {v}" for k, v in top))
    if new:
        lines.append("")
        lines.append("New this week:")
        for url, issue in new[:20]:
            lines.append(f"• {issue}: {url.replace(SITE, '') or '/'}")
        if len(new) > 20:
            lines.append(f"…and {len(new) - 20} more (see CSV)")
    return "\n".join(lines)


def write_csv(rows: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in COLUMNS})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--send", action="store_true", help="Telegram वर summary पाठवा")
    ap.add_argument("--limit", type=int, default=0, help="फक्त पहिली N पानं (test साठी)")
    args = ap.parse_args(argv)

    today = dt.date.today()
    urls = collect_urls(today.isocalendar()[1])
    if args.limit:
        urls = urls[:args.limit]
    if not urls:
        print("ERROR: no URLs found in sitemaps", file=sys.stderr)
        return 1
    print(f"Auditing {len(urls)} URLs…")
    rows = audit(urls)

    previous = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    first_run = not STATE_PATH.exists()
    state, new, fixed = compare(rows, previous)
    write_csv(rows)
    STATE_PATH.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    message = build_message(rows, new, fixed, today.isoformat())
    if first_run:
        message += "\n\n(First run: every current issue is listed as new.)"
    print(message)
    if args.send:
        from notify import _send_file, send_telegram  # private chat फक्त
        send_telegram(message)
        _send_file("sendDocument", "document", str(CSV_PATH), f"seo-audit-{today.isoformat()}.csv",
                   "text/csv", "SEO audit details")
    return 0


if __name__ == "__main__":
    sys.exit(main())
