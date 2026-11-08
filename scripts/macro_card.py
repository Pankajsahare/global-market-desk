"""
S3 — नवीन CPI / GDP जाहीर झाल्यावर 1080×1350 social image बनवून private Telegram वर पाठवतो.
तिथून तपासून मगच Instagram / LinkedIn / WhatsApp Status वर टाका.

    python scripts/macro_card.py --kind cpi --data public/log/macro.json --out macro-cpi.png [--send]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_photo  # noqa: E402
from snapshot import serve_and_open  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render India macro social card")
    parser.add_argument("--kind", choices=["cpi", "gdp"], required=True)
    parser.add_argument("--data", type=Path, default=Path("public/log/macro.json"))
    parser.add_argument("--out", type=Path, default=Path("macro-card.png"))
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args(argv)

    with serve_and_open(args.data, "macro-card.html", query=f"?kind={args.kind}") as page:
        page.locator("#snap").screenshot(path=str(args.out))
    print(f"Wrote {args.out}")
    if args.send:
        caption = f"India macro card ({args.kind.upper()} release). Review before posting."
        return 0 if send_photo(str(args.out), caption) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
