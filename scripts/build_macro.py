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
import os
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
LIMITS = {"gsec": (2.0, 15.0), "repo": (2.0, 12.0), "cpi": (-5.0, 25.0), "gdp": (-30.0, 30.0), "forex": (300.0, 1500.0)}

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
    # S1: base 2024 series 2026 पासून; त्याआधीचे महिने जुन्या base 2012 series मधून (chart पूर्ण 24 महिन्यांचा)
    first = min(points)
    wanted = sorted({f"{y:04d}-{m:02d}" for y in range(today.year - 3, today.year + 1) for m in range(1, 13)
                     if f"{y:04d}-{m:02d}" < first})[-max(months - len(points), 0):] if len(points) < months else []
    old_series: list[str] = []
    for year in sorted({int(p[:4]) for p in wanted}):
        for period, value in _cpi_2012(get, year).items():
            if period in wanted and period not in points:
                points[period] = value
                old_series.append(period)
    history = sorted(points.items())[-months:]
    period, value = history[-1]
    out = {"value": _check("cpi", value), "period": period, "source": "MoSPI (CPI, base 2024)",
           "history": [[p, round(v, 2)] for p, v in history]}
    linked = sorted(p for p in old_series if p >= history[0][0])
    if linked:
        out["base_2012_until"] = linked[-1]
    return out


def _cpi_2012(get: Fetch, year: int) -> dict[str, float]:
    """जुनी CPI (base 2012): All India, Combined, General Index ची महागाई; error आल्यास रिकामं."""
    found: dict[str, float] = {}
    page, pages = 1, 1
    while page <= pages and page <= 20:
        params = {"base_year": "2012", "series": "Current", "year": str(year), "state_code": "99",
                  "sector_code": "3", "Format": "JSON", "limit": 100}
        if page > 1:
            params["page"] = str(page)
        try:
            body = json.loads(get(MOSPI + "/api/cpi/getCPIIndex", params))
        except (ValueError, OSError) as exc:
            print(f"INFO: CPI 2012 {year} page {page}: {type(exc).__name__}: {exc}", file=sys.stderr)
            break
        pages = int((body.get("meta_data") or {}).get("totalPages") or 1)
        for row in body.get("data") or []:
            name = f"{row.get('group') or ''} {row.get('subgroup') or ''}".lower()
            if (row.get("sector") == "Combined" and "general" in name and row.get("month") in MONTHS
                    and _num(row.get("inflation")) is not None):
                found[f"{int(row['year']):04d}-{MONTHS.index(row['month']) + 1:02d}"] = _num(row["inflation"])
        page += 1
    if not found:
        print(f"INFO: CPI 2012 {year}: no General Index rows", file=sys.stderr)
    return found


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


# ---------- 10-year G-Sec (S5) ----------
RBI_HOME = "https://www.rbi.org.in/home.aspx"
_GSEC = re.compile(r"(\d+\.\d+)% GS (\d{4}) : (\d+\.\d+)%")


def parse_gsec(html: str, year: int) -> tuple[str, str, float] | None:
    """RBI home "Market Trends" मधून ~10 वर्षांचा benchmark bond: (तारीख, bond नाव, yield %)."""
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    start = text.find("Government Securities Market")
    if start < 0:
        return None
    block = text[start:start + 600]
    bonds = [(abs(int(maturity) - (year + 10)), f"{coupon}% GS {maturity}", float(rate))
             for coupon, maturity, rate in _GSEC.findall(block)]
    if not bonds:
        return None
    dates = re.findall(r"as on ([A-Z][a-z]+\.? \d{1,2}, \d{4})", block)
    _, name, rate = min(bonds)
    return (_wss_day(dates[0]) if dates else None) or "", name, rate


def fetch_gsec(get: Fetch, previous: dict[str, Any], today: datetime, keep: int = 260) -> dict[str, Any]:
    parsed = parse_gsec(get(RBI_HOME, None), today.year)
    if not parsed:
        raise ValueError("no G-Sec table")
    day, name, rate = parsed
    day = day or today.date().isoformat()
    _check("gsec", rate)
    history = {d: v for d, v in (previous.get("history") or [])}
    history[day] = round(rate, 4)
    ordered = sorted(history.items())[-keep:]
    week_ago = [v for d, v in ordered if d <= (datetime.fromisoformat(day) - timedelta(days=7)).date().isoformat()]
    return {"value": round(rate, 2), "bond": name, "as_of": day, "source": "RBI (Market Trends)",
            "change_week_bp": round((rate - week_ago[-1]) * 100) if week_ago else None,
            "history": [[d, v] for d, v in ordered]}


# ---------- repo line (S2) ----------
def repo_on(history: list[list[Any]], period: str) -> float | None:
    """त्या महिन्याच्या शेवटी लागू repo rate (history = [[YYYY-MM-DD, दर], ...])."""
    month_end = period + "-31"
    rates = [float(v) for d, v in sorted(history or []) if str(d) <= month_end]
    return rates[-1] if rates else None


# ---------- alerts (S1, S4) ----------
def release_alerts(previous: dict[str, Any], out: dict[str, Any]) -> list[str]:
    """नवीन CPI / GDP आकडा आला की private Telegram साठी संदेश + client WhatsApp draft (English)."""
    msgs = []
    old, new = previous.get("cpi") or {}, out.get("cpi") or {}
    if old.get("period") and new.get("period", "") > old["period"] and not new.get("stale"):
        month = datetime.strptime(new["period"], "%Y-%m").strftime("%B %Y")
        move = "up from" if new["value"] > old.get("value", new["value"]) else "down from"
        real = out.get("real_return")
        draft = (f"India's retail inflation (CPI) for {month} came in at {new['value']:.2f}%, {move} {old.get('value', 0):.2f}% "
                 f"the month before. ")
        if real:
            draft += (f"At today's bank FD rates of about {real['fd']:.2f}%, the return after inflation is roughly "
                      f"{real['value']:+.2f}% before tax. ")
        draft += "Want to review how your savings are placed? Reply here or visit https://www.advisor4u.in/global-market/"
        msgs.append(f"📊 CPI released: {new['value']:.2f}% ({month})\n\nClient WhatsApp draft (review before sending):\n{draft}")
    old, new = previous.get("gdp") or {}, out.get("gdp") or {}
    if old.get("period") and new.get("period") != old["period"] and not new.get("stale"):
        draft = (f"India's real GDP grew {new['value']:.1f}% in {new['period']}, compared with {old.get('value', 0):.1f}% "
                 f"in {old['period']}. See the full India macro snapshot: https://www.advisor4u.in/global-market/")
        msgs.append(f"📈 GDP released: {new['value']:.1f}% ({new['period']})\n\nClient WhatsApp draft (review before sending):\n{draft}")
    return msgs


def reminders(config: dict[str, Any], today: datetime) -> list[str]:
    """MPC नंतर repo rate बदलायचा राहिला / FD दर जुना → आठवड्यातून एकदा आठवण."""
    msgs, day = [], today.date()
    repo_as_of = str(config["repo_rate"].get("as_of", ""))
    held = [d for d in config.get("mpc_decisions", []) if d <= day.isoformat()]
    if held and repo_as_of < held[-1]:
        since = (day - datetime.fromisoformat(held[-1]).date()).days
        if since >= 3 and (since - 3) % 7 == 0:
            msgs.append(f"⏰ RBI MPC decision was on {held[-1]}. Please update repo_rate (value, as_of, history) in "
                        "global-market-desk/config/macro.json. If the rate was unchanged, just set as_of to the MPC date.")
    fd = config.get("fd_rate") or {}
    if fd.get("as_of"):
        age = (day - datetime.fromisoformat(fd["as_of"]).date()).days
        if age >= 60 and (age - 60) % 14 == 0:
            msgs.append(f"⏰ FD rate on the site ({fd.get('label', 'FD')} {fd.get('value')}%) was last checked {age} days ago. "
                        "Check sbi.co.in and update fd_rate in config/macro.json (set as_of even if unchanged).")
    return msgs


# ---------- data-अलार्म (S4) ----------
STALE_DAYS = {"cpi": 50, "gdp": 165, "forex": 16, "gsec": 7}  # पुढचा आकडा साधारण कधी येतो + थोडी सवलत


def _reference_day(key: str, item: dict[str, Any]) -> str | None:
    """आकडा कोणत्या दिवसाचा: CPI → महिन्याचा शेवट, GDP → तिमाहीचा शेवट, बाकी as_of."""
    if key == "cpi" and item.get("period"):
        year, month = map(int, item["period"].split("-"))
        nxt = datetime(year + month // 12, month % 12 + 1, 1)
        return (nxt - timedelta(days=1)).date().isoformat()
    if key == "gdp" and item.get("period"):
        m = re.match(r"Q(\d) FY(\d{2})-", item["period"])
        if not m:
            return None
        quarter, start = int(m.group(1)), 2000 + int(m.group(2))
        return {1: f"{start}-06-30", 2: f"{start}-09-30", 3: f"{start}-12-31", 4: f"{start + 1}-03-31"}[quarter]
    return item.get("as_of")


def stale_alerts(out: dict[str, Any], today: datetime) -> list[str]:
    """आकडा अपेक्षेपेक्षा जुना → source/format बदलला असेल; उशीर सुरू झाल्यापासून आठवड्यातून एकदा alert."""
    msgs = []
    for key, limit in STALE_DAYS.items():
        item = out.get(key)
        ref = _reference_day(key, item) if item else None
        if not ref:
            continue
        late = (today.date() - datetime.fromisoformat(ref).date()).days - limit
        if late >= 0 and late % 7 == 0:
            msgs.append(f"⚠️ Macro data looks stale: {key.upper()} is still for {item.get('period') or ref} "
                        f"({late + limit} days old). The source may have changed its format; check the Macro snapshot workflow log.")
    return msgs


# ---------- assemble ----------
def build(get: Fetch, config: dict[str, Any], previous: dict[str, Any], now: datetime,
          pause: Callable[[float], None] = time.sleep) -> tuple[dict[str, Any], list[str]]:
    """नवीन snapshot + fail झालेल्या sources ची यादी."""
    repo = dict(config["repo_rate"])
    repo["value"] = _check("repo", _num(repo["value"]))
    out: dict[str, Any] = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "repo": repo}
    fd = config.get("fd_rate")
    if fd and _num(fd.get("value")) is not None:
        out["fd"] = {**fd, "value": _check("repo", _num(fd["value"]))}
    failed: list[str] = []
    jobs = {
        "cpi": lambda: fetch_cpi(get, now, int(config.get("cpi_months", 24))),
        "gdp": lambda: fetch_gdp(get),
        "forex": lambda: fetch_forex(get, previous.get("forex") or {}, now, int(config.get("forex_weeks", 52)), pause),
        "gsec": lambda: fetch_gsec(get, previous.get("gsec") or {}, now),
    }
    for key, job in jobs.items():
        try:
            out[key] = job()
        except Exception as exc:  # noqa: BLE001 — source बंद असला तरी बाकीचे चालू राहतात
            print(f"WARN: {key} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(key)
            if previous.get(key):
                out[key] = {**previous[key], "stale": True}
    # CPI chart वर repo rate ची रेषा: प्रत्येक CPI महिन्याला लागू repo
    if out.get("cpi") and repo.get("history"):
        out["cpi"]["repo"] = [repo_on(repo["history"], period) for period, _ in out["cpi"]["history"]]
    # S2: real return = FD दर − CPI महागाई (दोन्ही ताजे असतील तेव्हाच)
    if out.get("fd") and out.get("cpi"):
        out["real_return"] = {"value": round(out["fd"]["value"] - out["cpi"]["value"], 2),
                              "fd": out["fd"]["value"], "cpi": out["cpi"]["value"], "cpi_period": out["cpi"]["period"]}
    return out, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/macro.json")
    parser.add_argument("--out", default="public/log/macro.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_path = Path(args.out)
    previous = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    now = datetime.now(timezone.utc)
    snapshot, failed = build(http_get, config, previous, now)
    if len(failed) == 4:
        print("ERROR: all macro sources failed; keeping previous file", file=sys.stderr)
        return 1
    ist = now + timedelta(hours=5, minutes=30)
    released = release_alerts(previous, snapshot)
    messages = released + reminders(config, ist) + stale_alerts(snapshot, ist)
    # S3: workflow ला सांगतो कोणत्या social card बनवायच्या
    kinds = [kind for kind, tag in (("cpi", "CPI released"), ("gdp", "GDP released")) if any(tag in m for m in released)]
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"releases={' '.join(kinds)}\n")
    same = {k: v for k, v in snapshot.items() if k != "updated"} == {k: v for k, v in previous.items() if k != "updated"}
    if same:
        print("macro.json unchanged")
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"macro.json written; failed: {failed or 'none'}")
    if messages:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from notify import send_telegram  # private chat only

        for text in messages:
            send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
