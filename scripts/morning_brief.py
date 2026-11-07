"""
S2 — Morning brief: live market.json वाचून cue + mood + top कारणं private Telegram chat वर पाठवतो.

वापर:
    python scripts/morning_brief.py --url https://<owner>.github.io/<repo>/data/market.json
    python scripts/morning_brief.py --file sample.json --dry-run   # फक्त message छापा
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_telegram  # noqa: E402
from signals import compute_cue, compute_mood, index_items  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
STALE_MINUTES = 90
# TODO [मॅन्युअल बदल]: private dashboard चा link | न बदलल्यास: brief मध्ये चुकीचा link
DASHBOARD_URL = "https://www.advisor4u.in/global-market-private/"  # ← येथे बदला


def _pct(v: Any) -> str:
    return f"{v:+.2f}%" if isinstance(v, (int, float)) else "n/a"


def _last(mapping: dict, symbol: str, digits: int = 2) -> str:
    item = mapping.get(symbol)
    if not item or not isinstance(item.get("last"), (int, float)):
        return "n/a"
    return f"{item['last']:,.{digits}f}"


def build_message(data: dict[str, Any], now: datetime | None = None) -> str:
    """market.json → Telegram message (plain text, English)."""
    now = now or datetime.now(IST)
    mapping, globals_ = index_items(data)
    cue = compute_cue(mapping)
    mood = compute_mood(mapping, globals_)

    lines = [
        f"🌏 Morning Desk — {now.strftime('%d %b %Y, %H:%M')} IST",
        "",
        f"India open cue: {cue['label']} (score {cue['score']:+.2f})",
        f"Risk mood: {mood['label']} ({mood['score']}/100)",
    ]

    updated = data.get("updated")
    if updated:
        age = (now - datetime.fromisoformat(updated).astimezone(IST)).total_seconds() / 60
        if age > STALE_MINUTES:
            lines.append(f"⚠️ Data is {int(age)} minutes old")

    lines += ["", "Cue components (1D move):"]
    for row in cue["rows"]:
        lines.append(f"• {row['label']} ({int(row['weight'] * 100)}%): {_pct(row['move'])}")

    top = sorted((r for r in mood["reasons"] if r[0] != 0), key=lambda r: -abs(r[0]))[:3]
    if top:
        lines += ["", "Top mood drivers:"]
        lines += [f"{pts:+d}  {text}" for pts, text in top]

    tnx = mapping.get("^TNX", {})
    tnx_last = tnx.get("last")
    tnx_text = f"{(tnx_last / 10 if tnx_last > 20 else tnx_last):.2f}%" if isinstance(tnx_last, (int, float)) else "n/a"
    lines += [
        "",
        f"India VIX {_last(mapping, '^INDIAVIX')} · US 10Y {tnx_text} · "
        f"USD/INR {_last(mapping, 'INR=X')} · Brent {_last(mapping, 'BZ=F')} · Gold {_last(mapping, 'GC=F', 1)}",
        "",
        f"Dashboard: {DASHBOARD_URL}",
        "Delayed data. Internal use only — not investment advice.",
    ]
    return "\n".join(lines)


def load_data(url: str | None, file: Path | None) -> dict[str, Any]:
    if file:
        return json.loads(file.read_text(encoding="utf-8"))
    # CDN cache टाळण्यासाठी query string
    bust = int(datetime.now(timezone.utc).timestamp() // 60)
    with urllib.request.urlopen(f"{url}?b={bust}", timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send Morning Desk brief to Telegram")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="message फक्त छापा, पाठवू नका")
    args = parser.parse_args(argv)

    try:
        data = load_data(args.url, args.file)
    except Exception as exc:  # noqa: BLE001 — कोणतीही fetch error → alert message
        print(f"ERROR: could not load data: {exc}", file=sys.stderr)
        if not args.dry_run:
            send_telegram("⚠️ Morning Desk: market data could not be loaded today. Check GitHub Actions.")
        return 1

    message = build_message(data)
    print(message)
    if args.dry_run:
        return 0
    return 0 if send_telegram(message) else 1


if __name__ == "__main__":
    sys.exit(main())
