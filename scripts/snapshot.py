"""
S5 — रोजचा social snapshot PNG बनवून private Telegram वर पाठवतो.

    python scripts/snapshot.py --data public/data/market.json --out snapshot.png [--send]

public/ folder local server वर चालवून widget/snapshot.html headless Chromium मध्ये उघडतो.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_photo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # access logs नकोत
        pass


def render(data_file: Path, out: Path) -> None:
    """Snapshot page + data एका temp folder मध्ये serve करून PNG घ्या."""
    from playwright.sync_api import sync_playwright  # workflow मध्येच install होतो

    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        (site / "widget").mkdir()
        (site / "data").mkdir()
        shutil.copy(ROOT / "public" / "widget" / "snapshot.html", site / "widget" / "snapshot.html")
        shutil.copy(data_file, site / "data" / "market.json")

        handler = functools.partial(_QuietHandler, directory=str(site))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1080, "height": 1350})
                page.goto(f"http://127.0.0.1:{server.server_port}/widget/snapshot.html")
                page.wait_for_selector("body[data-ready]", timeout=15000)
                if page.get_attribute("body", "data-ready") != "1":
                    raise RuntimeError("snapshot page could not load data")
                page.locator("#snap").screenshot(path=str(out))
                browser.close()
        finally:
            server.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render daily social snapshot")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("snapshot.png"))
    parser.add_argument("--send", action="store_true", help="Telegram private chat वर पाठवा")
    args = parser.parse_args(argv)

    render(args.data, args.out)
    print(f"Wrote {args.out}")
    if args.send:
        today = datetime.now(IST).strftime("%d %b %Y")
        caption = (f"Global Markets snapshot — {today}\n"
                   "Public data only. Review before posting.")
        return 0 if send_photo(str(args.out), caption) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
