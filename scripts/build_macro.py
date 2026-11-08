"""India Macro Snapshot: repo rate, CPI महागाई, GDP वाढ, forex reserves → public/log/macro.json.

Sources (सर्व मोफत, key नाही):
- CPI (base 2024) आणि GDP growth: MoSPI eSankhyiki API (api.mospi.gov.in)
- Forex reserves: RBI Weekly Statistical Supplement (rbi.org.in)
- Repo rate: config/macro.json (प्रत्येक MPC नंतर हाताने बदलायचा)

एखादा source fail झाला तर त्याचा मागचा value "stale": true सह ठेवतो; सगळेच fail → file बदलत नाही.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable

MOSPI = "https://api.mospi.gov.in"
RBI_WSS = "https://www.rbi.org.in/Scripts/BS_viewWssExtract.aspx"
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
# अशक्य आकडा आला तर तो source चुकला असं मानतो
LIMITS = {"repo": (2.0, 12.0), "cpi": (-5.0, 25.0), "gdp": (-30.0, 30.0), "forex": (300.0, 1500.0)}

# TLS verification चालू; MoSPI/RBI च्या जुन्या servers साठी फक्त legacy renegotiation परवानगी
_CTX = ssl.create_default_context()
_CTX.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)

Fetch = Callable[[str, "dict[str, Any] | None"], str]


def http_get(url: str, params: dict[str, Any] | None = None) -> str:
    """साधा GET; error आल्यास exception (caller ठरवतो काय करायचं)."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (advisor4u macro bot)"})
    with urllib.request.urlopen(request, timeout=45, context=_CTX) as response:
        return response.read().decode("utf-8", "replace")


def _num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _check(kind: str, value: float | None) -> float:
    low, high = LIMITS[kind]
    if value is None or not low <= value <= high:
        raise ValueError(f"{kind} value out of range: {value}")
    return round(value, 2)


# ---------- CPI ----------
def fetch_cpi(get: Fetch, today: datetime, months: int) -> dict[str, Any]:
    """All India, Combined, CPI (General) ची वार्षिक महागाई (%), शेवटचे `months` महिने."""
    points: dict[str, float] = {}
    # Base 2024 series 2025 पासूनच आहे; प्रत्येक वर्ष वेगळं मागतो, नसलेलं वर्ष वगळतो
    for year in range(today.year - months // 12, today.year + 1):
        # division_code 0 = CPI (General), sector_code 3 = Combined → वर्षाला जास्तीत जास्त 12 ओळी
        try:
            body = json.loads(get(MOSPI + "/api/cpi/getCPIData", {
                "base_year": "2024", "series": "Current", "year": str(year), "state_code": "1",
                "division_code": "0", "sector_code": "3", "Format": "JSON", "limit": 50}))
        except (ValueError, urllib.error.HTTPError) as exc:
            print(f"INFO: CPI {year}: {type(exc).__name__}: {exc}", file=sys.stderr)  # ते वर्ष series मध्ये नाही
            continue
        for row in body.get("data") or []:
            if (row.get("state") == "All India" and row.get("sector") == "Combined"
                    and row.get("division") == "CPI (General)" and row.get("month") in MONTHS):
                value = _num(row.get("inflation"))
                if value is not None:
                    points[f"{int(row['year']):04d}-{MONTHS.index(row['month']) + 1:02d}"] = value
    if not points:
        raise ValueError("no CPI rows")
    history = sorted(points.items())[-months:]
    period, value = history[-1]
    return {"value": _check("cpi", value), "period": period, "source": "MoSPI (CPI, base 2024)",
            "history": [[p, round(v, 2)] for p, v in history]}


# ---------- GDP ----------
def _quarter_key(row: dict[str, Any]) -> tuple[int, int]:
    return int(str(row["year"])[:4]), int(str(row["quarter"]).lstrip("Q"))


def fetch_gdp(get: Fetch) -> dict[str, Any]:
    """तिमाही real GDP growth (constant prices, base 2022-23)."""
    body = json.loads(get(MOSPI + "/api/nas/getNASData", {
        "base_year": "2022-23", "series": "Current", "frequency_code": "Quarterly",
        "indicator_code": 22, "limit": 100}))
    rows = [r for r in body.get("data") or []
            if r.get("quarter") and r.get("year") and _num(r.get("constant_price")) is not None]
    if not rows:
        raise ValueError("no GDP rows")
    rows.sort(key=_quarter_key)
    history = [[f"{r['quarter']} FY{str(r['year'])[2:4]}-{str(r['year'])[-2:]}", _num(r["constant_price"])]
               for r in rows][-8:]
    period, value = history[-1]
    return {"value": _check("gdp", value), "period": period,
            "source": "MoSPI (real GDP, base 2022-23)", "history": history}


# ---------- Forex reserves ----------
_WSS = re.compile(r"Foreign Exchange Reserves.*?As on ([A-Z][a-z]+\.? \d{1,2}, \d{4}).*?Total Reserves\s+"
                  r"(-?[\d,]+)\s+(-?[\d,]+)\s+(-?[\d,]+)\s+(-?[\d,]+)", re.S)


def _wss_day(text: str) -> str | None:
    """RBI तारीख कधी "October 30, 2026", कधी "Jul. 03, 2026" / "Sept. 4, 2026" लिहितो."""
    clean = text.replace(".", "").replace("Sept ", "Sep ")
    for pattern in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(clean, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def parse_wss(html: str) -> tuple[str, float, float] | None:
    """WSS पानातून (तारीख, total US$ bn, आठवड्याचा बदल US$ bn)."""
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    match = _WSS.search(text)
    if not match:
        return None
    day = _wss_day(match.group(1))
    if day is None:
        return None
    usd_mn, week_usd_mn = _num(match.group(3)), _num(match.group(5))
    if usd_mn is None or week_usd_mn is None:
        return None
    return day, round(usd_mn / 1000, 2), round(week_usd_mn / 1000, 2)


def wss_dates(get: Fetch) -> list[str]:
    """RBI WSS यादीतील उपलब्ध तारखा (MM/DD/YYYY)."""
    return re.findall(r"SelectedDate=(\d{2}/\d{2}/\d{4})", get(RBI_WSS, None))


def fetch_forex(get: Fetch, previous: dict[str, Any], today: datetime, weeks: int,
                pause: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """नवीनतम आठवडा + जुना इतिहास; इतिहास कमी असल्यास मागचे शुक्रवार भरतो (पहिल्यांदाच)."""
    history = {d: v for d, v in (previous.get("history") or [])}
    change = previous.get("change_week")
    targets = wss_dates(get)[:1]
    if len(history) < weeks // 2:
        # WSS दर शुक्रवारी येतो; मागचे शुक्रवार (आजपासून)
        friday = today - timedelta(days=(today.weekday() - 4) % 7)
        # सुट्टी असल्यास WSS गुरुवारी येतो — म्हणून शुक्रवार न मिळाल्यास गुरुवार
        targets += [[(friday - timedelta(weeks=i, days=back)).strftime("%m/%d/%Y") for back in (0, 1)]
                    for i in range(1, weeks + 4)]
    newest = None
    for target in targets:
        parsed = None
        for selected in ([target] if isinstance(target, str) else target):
            try:
                parsed = parse_wss(get(RBI_WSS, {"SelectedDate": selected}))
            except Exception:  # noqa: BLE001 — एक आठवडा चुकला तरी बाकी चालू
                parsed = None
            pause(1.0)  # RBI server वर भार नको
            if parsed:
                break
        if parsed:
            day, total, week = parsed
            history[day] = _check("forex", total)
            if newest is None or day > newest[0]:
                newest = (day, week)
    if not history:
        raise ValueError("no forex data")
    ordered = sorted(history.items())[-weeks:]
    as_of, value = ordered[-1]
    if newest and newest[0] == as_of:
        change = newest[1]
    return {"value": value, "as_of": as_of, "change_week": change,
            "source": "RBI Weekly Statistical Supplement", "history": [[d, v] for d, v in ordered]}


# ---------- assemble ----------
def build(get: Fetch, config: dict[str, Any], previous: dict[str, Any], now: datetime,
          pause: Callable[[float], None] = time.sleep) -> tuple[dict[str, Any], list[str]]:
    """नवीन snapshot + fail झालेल्या sources ची यादी."""
    repo = dict(config["repo_rate"])
    repo["value"] = _check("repo", _num(repo["value"]))
    out: dict[str, Any] = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "repo": repo}
    failed: list[str] = []
    jobs = {
        "cpi": lambda: fetch_cpi(get, now, int(config.get("cpi_months", 24))),
        "gdp": lambda: fetch_gdp(get),
        "forex": lambda: fetch_forex(get, previous.get("forex") or {}, now, int(config.get("forex_weeks", 52)), pause),
    }
    for key, job in jobs.items():
        try:
            out[key] = job()
        except Exception as exc:  # noqa: BLE001 — source बंद असला तरी बाकीचे चालू राहतात
            print(f"WARN: {key} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(key)
            if previous.get(key):
                out[key] = {**previous[key], "stale": True}
    return out, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/macro.json")
    parser.add_argument("--out", default="public/log/macro.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_path = Path(args.out)
    previous = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    snapshot, failed = build(http_get, config, previous, datetime.now(timezone.utc))
    if len(failed) == 3:
        print("ERROR: all macro sources failed; keeping previous file", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"macro.json written; failed: {failed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
