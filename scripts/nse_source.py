"""
S3 — Indian indices साठी दुसरा source: NSE चा /api/allIndices (Yahoo fail झाल्यासच).

NSE website ला browser सारखे headers आणि cookies लागतात (invest-core मधल्या पद्धतीप्रमाणे):
आधी एक पान उघडून cookies घेतो, मग API. एका run मध्ये API एकदाच बोलावला जातो.
NSE कडे daily history नाही, त्यामुळे 3M return आणि sparkline मागच्या डेटावरून (असल्यास) येतात.
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Callable, Optional

NSE_WEB = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE_WEB}/all-reports",
}

Row = dict[str, Any]


def _get(opener, url: str) -> Optional[bytes]:
    try:
        with opener.open(urllib.request.Request(url, headers=HEADERS), timeout=20) as response:
            return response.read() if response.status == 200 else None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def fetch_all_indices() -> dict[str, Row]:
    """{INDEX NAME (upper): row}. काहीही fail झाल्यास रिकामं."""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    if _get(opener, f"{NSE_WEB}/all-reports") is None:
        print("WARN NSE: could not open website (cookies)", file=sys.stderr)
        return {}
    body = _get(opener, f"{NSE_WEB}/api/allIndices")
    if body is None:
        print("WARN NSE: allIndices unavailable", file=sys.stderr)
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    stamp = payload.get("timestamp")
    rows: dict[str, Row] = {}
    for row in payload.get("data") or []:
        name = str(row.get("index") or row.get("indexSymbol") or "").upper()
        if name:
            rows[name] = {**row, "_timestamp": stamp}
    return rows


class NseIndices:
    """Lazy: पहिल्यांदा गरज लागेल तेव्हाच NSE ला एकदा बोलावतो."""

    def __init__(self, fetcher: Callable[[], dict[str, Row]] = fetch_all_indices):
        self._fetcher = fetcher
        self._rows: Optional[dict[str, Row]] = None

    def get(self, name: str) -> Optional[Row]:
        if self._rows is None:
            self._rows = self._fetcher()
        return self._rows.get(name.upper())


def _num(row: Row, *keys: str) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        try:
            if value not in (None, "", "-"):
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _pct(last: Optional[float], base: Optional[float]) -> Optional[float]:
    if last is None or not base:
        return None
    return round((last - base) / base * 100, 2)


def _asof(stamp: Any) -> Optional[str]:
    """NSE timestamp "07-Nov-2026 15:30:00" → "2026-11-07"."""
    if not isinstance(stamp, str):
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(stamp.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def nse_item(cfg: dict[str, Any], row: Row, previous: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    """NSE row → dashboard item (Yahoo item सारखेच keys)."""
    last = _num(row, "last")
    prev_close = _num(row, "previousClose", "previousDay")
    if last is None or prev_close is None:
        return None
    decimals = int(cfg.get("decimals", 2))
    week = _num(row, "oneWeekAgoVal", "oneWeekAgo")
    month = _num(row, "oneMonthAgoVal", "oneMonthAgo")
    year = _num(row, "oneYearAgoVal", "oneYearAgo")
    r1m = _num(row, "perChange30d")
    r1y = _num(row, "perChange365d")
    item: dict[str, Any] = {
        "symbol": cfg["symbol"],
        "name": cfg["name"],
        "last": round(last, decimals),
        "r1d": _pct(last, prev_close),
        "d1d": round(last - prev_close, decimals),
        "r1w": _pct(last, week),
        "r1m": round(r1m, 2) if r1m is not None else _pct(last, month),
        "r3m": (previous or {}).get("r3m"),            # NSE कडे नाही → मागचं मूल्य
        "r1y": round(r1y, 2) if r1y is not None else _pct(last, year),
        "d1w": round(last - week, decimals) if week is not None else None,
        "asof": _asof(row.get("_timestamp")),
        "marketTime": None,
        "spark": list((previous or {}).get("spark") or []),
        "stale": False,
        "sourceSymbol": f"nse:{cfg['nse']}",
    }
    for extra in ("region", "category"):
        if extra in cfg:
            item[extra] = cfg[extra]
    return item
