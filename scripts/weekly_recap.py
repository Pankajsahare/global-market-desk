"""
S5 — Weekly Market Recap PDF (A4) बनवून private Telegram वर पाठवतो.
तिथून तुम्ही वाचून clients ना WhatsApp वर forward करा.

    python scripts/weekly_recap.py --data public/data/market.json --out recap.pdf [--send]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_document  # noqa: E402
from snapshot import serve_and_open  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Weekly Market Recap PDF")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("weekly-recap.pdf"))
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args(argv)

    with serve_and_open(args.data, "weekly.html", viewport=(794, 1123)) as page:
        page.pdf(path=str(args.out), format="A4", print_background=True,
                 margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    print(f"Wrote {args.out}")

    if args.send:
        data = json.loads(args.data.read_text(encoding="utf-8"))
        dates = [g.get("asof") for g in (data.get("groups") or {}).get("global", []) if g.get("asof")]
        week = max(dates) if dates else date.today().isoformat()
        name = f"Weekly-Market-Recap-{week}.pdf"
        caption = f"Weekly Market Recap — week ended {week}\nReview before forwarding to clients."
        return 0 if send_document(str(args.out), caption, filename=name) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
