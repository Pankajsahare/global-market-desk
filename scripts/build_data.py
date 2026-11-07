"""
Global Market Desk — data builder.

Yahoo Finance v8 chart API वरून config मधल्या सर्व symbols चा daily डेटा आणतो,
returns (1D/1W/1M/3M/1Y) काढतो आणि public/data/market.json लिहितो.
फक्त Python standard library — काहीही install करावं लागत नाही.

वापर:
    python scripts/build_data.py --config config/symbols.json \
        --out public/data/market.json --previous previous.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summary import build_summary, build_weekly_summary  # noqa: E402  (S2, S5)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2y"
USER_AGENT = "Mozilla/5.0 (compatible; GlobalMarketDesk/1.0; +https://www.advisor4u.in)"
REQUEST_TIMEOUT = 15        # seconds
RETRIES = 2                 # पहिल्या प्रयत्नानंतर किती वेळा पुन्हा
PAUSE_SECONDS = 0.4         # दोन requests मधला gap (rate-limit टाळण्यासाठी)
SPARK_POINTS = 66           # sparkline साठी शेवटचे ~3 महिने
MIN_SUCCESS_RATIO = 0.5     # यापेक्षा कमी यश → नवीन file लिहू नका
INDEX_MAX_AGE_DAYS = 7      # invest-core index डेटा यापेक्षा जुना → Yahoo वापरा

# return चे नाव → किती calendar दिवस मागे
RETURN_WINDOWS = {"r1w": 7, "r1m": 30, "r3m": 91, "r1y": 365}

Series = list[tuple[str, float]]


def fetch_chart(symbol: str) -> Optional[dict[str, Any]]:
    """एका symbol चा Yahoo chart result आणा; fail झाल्यास None."""
    url = YAHOO_URL.format(symbol=urllib.parse.quote(symbol, safe=""))
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = (payload.get("chart") or {}).get("result") or []
            return results[0] if results else None
        except urllib.error.HTTPError as exc:
            print(f"WARN {symbol}: HTTP {exc.code} (attempt {attempt + 1})", file=sys.stderr)
            if exc.code == 404:
                return None  # symbol चुकीचा — पुन्हा प्रयत्न व्यर्थ
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            print(f"WARN {symbol}: {exc} (attempt {attempt + 1})", file=sys.stderr)
        if attempt < RETRIES:
            time.sleep(2 * (attempt + 1))  # 429/5xx वर थोडं थांबा
    return None


def parse_series(result: dict[str, Any]) -> Series:
    """Timestamps + closes → [(YYYY-MM-DD, close)] — null वगळून, एका दिवसाचा एकच bar."""
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    offset = int((result.get("meta") or {}).get("gmtoffset") or 0)  # exchange चा timezone

    by_date: dict[str, float] = {}
    for ts, close in zip(timestamps, closes):
        if not isinstance(close, (int, float)) or isinstance(close, bool):
            continue
        day = datetime.fromtimestamp(int(ts) + offset, tz=timezone.utc).date().isoformat()
        by_date[day] = float(close)  # same date चा नंतरचा bar जुन्याला replace करतो
    return sorted(by_date.items())


def close_on_or_before(series: Series, target: date) -> Optional[float]:
    """दिलेल्या तारखेला किंवा त्याआधीचा शेवटचा close (सुट्टीसाठी)."""
    target_iso = target.isoformat()
    for day, value in reversed(series):
        if day <= target_iso:
            return value
    return None


def pct_change(current: float, base: Optional[float]) -> Optional[float]:
    if base is None or base == 0:
        return None
    return round((current - base) / base * 100, 2)


def build_item(cfg: dict[str, Any], result: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Config entry + Yahoo result → dashboard item. डेटा अपुरा असल्यास None."""
    market_time = (result.get("meta") or {}).get("regularMarketTime")
    return item_from_series(cfg, parse_series(result), market_time)


def item_from_series(cfg: dict[str, Any], series: Series, market_time: Any = None) -> Optional[dict[str, Any]]:
    """[(date, close)] series → dashboard item (Yahoo किंवा invest-core दोन्हीसाठी)."""
    if len(series) < 2:
        return None

    decimals = int(cfg.get("decimals", 2))
    last_day, last = series[-1]
    prev = series[-2][1]
    last_date = date.fromisoformat(last_day)

    item: dict[str, Any] = {
        "symbol": cfg["symbol"],
        "name": cfg["name"],
        "last": round(last, decimals),
        "r1d": pct_change(last, prev),
        "d1d": round(last - prev, decimals),
    }
    for key, days in RETURN_WINDOWS.items():
        item[key] = pct_change(last, close_on_or_before(series, last_date - timedelta(days=days)))

    week_base = close_on_or_before(series, last_date - timedelta(days=7))
    item["d1w"] = round(last - week_base, decimals) if week_base is not None else None

    item["asof"] = last_day
    item["marketTime"] = (
        datetime.fromtimestamp(int(market_time), tz=timezone.utc).isoformat()
        if isinstance(market_time, (int, float))
        else None
    )
    item["spark"] = [round(value, decimals) for _, value in series[-SPARK_POINTS:]]
    item["stale"] = False

    # optional config fields frontend ला पुढे पाठवा
    for extra in ("region", "category"):
        if extra in cfg:
            item[extra] = cfg[extra]
    return item


def load_previous(path: Optional[Path]) -> dict[str, dict[str, Any]]:
    """मागचा market.json → {symbol: item}. File नसल्यास/खराब असल्यास रिकामं."""
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    previous: dict[str, dict[str, Any]] = {}
    for items in (data.get("groups") or {}).values():
        for item in items or []:
            if isinstance(item, dict) and "symbol" in item:
                previous[item["symbol"]] = item
    return previous


def load_index_proxies(path: Optional[Path]) -> dict[str, Series]:
    """S6: invest-core ने publish केलेले NSE index closes → {index name: [(date, close)]}."""
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    out: dict[str, Series] = {}
    for name, rows in (data.get("series") or {}).items():
        clean = sorted((str(d), float(c)) for d, c in rows if isinstance(c, (int, float)))
        if clean:
            out[name] = clean
    return out


def index_item(cfg: dict[str, Any], index_series: dict[str, Series], today: date) -> Optional[dict[str, Any]]:
    """Config मध्ये "indexHistory" असल्यास आणि डेटा ताजा (≤ INDEX_MAX_AGE_DAYS) असल्यास item."""
    name = cfg.get("indexHistory")
    series = index_series.get(name) if name else None
    if not series or len(series) < int(cfg.get("minPoints", 2)):
        return None
    if (today - date.fromisoformat(series[-1][0])).days > INDEX_MAX_AGE_DAYS:
        print(f"WARN {name}: index history is stale, using Yahoo", file=sys.stderr)
        return None
    item = item_from_series({**cfg, "name": cfg.get("indexName", name)}, series)
    if item is not None:
        item["sourceSymbol"] = f"invest-core:{name}"
    return item


def build_dataset(
    config: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    fetcher=fetch_chart,
    pause: float = PAUSE_SECONDS,
    index_series: Optional[dict[str, Series]] = None,
    today: Optional[date] = None,
) -> tuple[dict[str, Any], int, int]:
    """सर्व groups साठी डेटा बनवा. Returns (dataset, success_count, total_count)."""
    groups_out: dict[str, list[dict[str, Any]]] = {}
    success = total = 0

    for group_name, entries in (config.get("groups") or {}).items():
        items: list[dict[str, Any]] = []
        for cfg in entries:
            total += 1
            # S6: invest-core चा खरा index डेटा आधी; नसल्यास/जुना असल्यास Yahoo
            item = index_item(cfg, index_series or {}, today or datetime.now(timezone.utc).date())
            if item is not None:
                success += 1
                items.append(item)
                continue
            best_points = -1
            min_points = int(cfg.get("minPoints", 2))
            # आधी मुख्य symbol, मग "fallbacks" क्रमाने. पुरेसा history (minPoints) मिळाला की थांबा;
            # कोणालाच नाही मिळाला तर सर्वात लांब history असलेला वापरा.
            for candidate in [cfg] + list(cfg.get("fallbacks") or []):
                result = fetcher(candidate["symbol"])
                if not result:
                    continue
                points = len(parse_series(result))
                built = build_item({**cfg, "name": candidate.get("name", cfg["name"]),
                                    "symbol": candidate["symbol"]}, result)
                if built is None or points <= best_points:
                    continue
                built["symbol"] = cfg["symbol"]          # frontend साठी key स्थिर
                built["sourceSymbol"] = candidate["symbol"]
                item, best_points = built, points
                if points >= min_points:
                    break
                print(f"WARN {candidate['symbol']}: only {points} points (< {min_points}), trying fallback",
                      file=sys.stderr)
            if item is not None:
                success += 1
                items.append(item)
            elif cfg["symbol"] in previous:
                # fail → मागचा डेटा, पण stale म्हणून चिन्हांकित
                stale_item = dict(previous[cfg["symbol"]])
                stale_item["stale"] = True
                items.append(stale_item)
            else:
                print(f"WARN {cfg['symbol']}: no data, skipped", file=sys.stderr)
            if pause:
                time.sleep(pause)
        groups_out[group_name] = items

    dataset = {
        "updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "Yahoo Finance (unofficial, delayed)",
        "summary": build_summary(groups_out),
        "weeklySummary": build_weekly_summary(groups_out),
        "groups": groups_out,
    }
    return dataset, success, total


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """आधी .tmp मध्ये लिहा, मग rename — अर्धवट file कधीच publish होत नाही."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build market.json for Global Market Desk")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--previous", type=Path, default=None)
    parser.add_argument("--index-proxies", type=Path, default=Path("data-in/index_proxies.json"))
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    previous = load_previous(args.previous)
    dataset, success, total = build_dataset(config, previous, index_series=load_index_proxies(args.index_proxies))

    print(f"Fetched {success}/{total} symbols")
    if total == 0 or success / total < MIN_SUCCESS_RATIO:
        # Exit 1 → workflow deploy होत नाही → site वर मागचा डेटा तसाच राहतो
        print("ERROR: too many symbols failed; keeping previous deployment", file=sys.stderr)
        return 1

    write_json_atomic(args.out, dataset)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
