"""
S3 — Cue accuracy tracker.

record   : सकाळचा cue log मध्ये नोंदवा (morning_brief.py मधून बोलावला जातो)
evaluate : दुपारी NIFTY 50 चा opening gap (open vs मागचा close) पाहून cue बरोबर ठरला का ते लिहा

    python scripts/cue_tracker.py evaluate --log public/log/cue-log.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

IST = timezone(timedelta(hours=5, minutes=30))
NIFTY = "^NSEI"
CUE_BAND = 0.15      # cue score: ≥ +0.15 = up, ≤ −0.15 = down, मधे = flat
GAP_BAND = 0.15      # NIFTY gap %: ≥ +0.15% = up, ≤ −0.15% = down, मधे = flat
MAX_ENTRIES = 400    # log फार मोठा होऊ नये
EVAL_AFTER_HOUR = 16 # आजची नोंद 16:00 IST नंतरच "holiday" ठरवा


def direction(value: float, band: float) -> str:
    if value >= band:
        return "up"
    if value <= -band:
        return "down"
    return "flat"


def load_log(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"entries": []}
    if not isinstance(data.get("entries"), list):
        data["entries"] = []
    return data


def save_log(path: Path, data: dict[str, Any]) -> None:
    data["entries"] = data["entries"][-MAX_ENTRIES:]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def record(path: Path, cue: dict[str, Any], mood: dict[str, Any], now: datetime) -> bool:
    """आजचा cue नोंदवा. Weekend ला skip. आधीची pending नोंद असल्यास replace; done असल्यास बदलू नका."""
    today = now.astimezone(IST).date()
    if today.weekday() >= 5:
        print("Weekend — cue not recorded")
        return False
    data = load_log(path)
    entry = {
        "date": today.isoformat(),
        "recordedAt": now.astimezone(IST).replace(microsecond=0).isoformat(),
        "cueScore": round(cue["score"], 3),
        "cueLabel": cue["label"],
        "cueDir": direction(cue["score"], CUE_BAND),
        "mood": mood["score"],
        "moodLabel": mood["label"],
        "actualGapPct": None,
        "actualDir": None,
        "hit": None,
        "status": "pending",
    }
    for i, existing in enumerate(data["entries"]):
        if existing.get("date") == entry["date"]:
            if existing.get("status") != "pending":
                return False  # आधीच evaluate झालेली नोंद बदलू नका
            data["entries"][i] = entry
            break
    else:
        data["entries"].append(entry)
    save_log(path, data)
    print(f"Recorded cue for {entry['date']}: {entry['cueLabel']} ({entry['cueScore']:+.2f})")
    return True


def parse_bars(result: dict[str, Any]) -> list[tuple[str, Optional[float], Optional[float]]]:
    """Yahoo result → [(date, open, close)] तारखेनुसार sorted."""
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens, closes = quote.get("open") or [], quote.get("close") or []
    offset = int((result.get("meta") or {}).get("gmtoffset") or 0)
    bars: dict[str, tuple[Optional[float], Optional[float]]] = {}
    for i, ts in enumerate(timestamps):
        day = datetime.fromtimestamp(int(ts) + offset, tz=timezone.utc).date().isoformat()
        o = opens[i] if i < len(opens) and isinstance(opens[i], (int, float)) else None
        c = closes[i] if i < len(closes) and isinstance(closes[i], (int, float)) else None
        if o is not None or c is not None:
            bars[day] = (o, c)
    return [(d, o, c) for d, (o, c) in sorted(bars.items())]


def evaluate(path: Path, fetcher: Callable[[str], Optional[dict]], now: datetime) -> int:
    """Pending नोंदी NIFTY च्या opening gap शी तपासा. किती नोंदी बदलल्या ते return."""
    data = load_log(path)
    pending = [e for e in data["entries"] if e.get("status") == "pending"]
    if not pending:
        print("No pending entries")
        return 0

    result = fetcher(NIFTY)
    if not result:
        print("ERROR: NIFTY data unavailable; will retry next run", file=sys.stderr)
        return 0
    bars = parse_bars(result)
    index = {d: i for i, (d, _, _) in enumerate(bars)}
    now_ist = now.astimezone(IST)
    today = now_ist.date()

    changed = 0
    for entry in pending:
        day = entry["date"]
        i = index.get(day)
        if i is None or i == 0:
            entry_day = date.fromisoformat(day)
            if entry_day < today or (entry_day == today and now_ist.hour >= EVAL_AFTER_HOUR):
                if i is None:
                    entry["status"] = "holiday"   # त्या दिवशी NSE बंद
                    changed += 1
            continue
        open_, prev_close = bars[i][1], bars[i - 1][2]
        if open_ is None or prev_close in (None, 0):
            continue
        if abs(open_ - prev_close) < 1e-9:
            entry["status"] = "suspect"  # Yahoo ने open = मागचा close दिला — विश्वासार्ह नाही
            changed += 1
            continue
        gap = round((open_ - prev_close) / prev_close * 100, 3)
        entry["actualGapPct"] = gap
        entry["actualDir"] = direction(gap, GAP_BAND)
        entry["hit"] = entry["actualDir"] == entry.get("cueDir")
        entry["status"] = "done"
        changed += 1
        print(f"{day}: cue {entry['cueDir']} vs gap {gap:+.2f}% ({entry['actualDir']}) → "
              f"{'HIT' if entry['hit'] else 'MISS'}")

    if changed:
        save_log(path, data)
    return changed


def hit_rate(data: dict[str, Any], window: int = 30) -> Optional[tuple[int, int]]:
    """शेवटच्या `window` evaluated sessions मध्ये (hits, total)."""
    done = [e for e in data.get("entries", []) if e.get("status") == "done"][-window:]
    if not done:
        return None
    return sum(1 for e in done if e.get("hit") is True), len(done)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cue accuracy tracker")
    parser.add_argument("command", choices=["evaluate"])
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)

    from build_data import fetch_chart  # network फक्त evaluate साठी लागतो
    evaluate(args.log, fetch_chart, datetime.now(timezone.utc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
