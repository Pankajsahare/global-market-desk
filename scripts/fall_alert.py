"""
S2 — मोठ्या घसरणीचा alert + clients साठी WhatsApp message चा draft (private Telegram वर).

नियम (भारतीय बाजार चालू असताना, फक्त आजच्या डेटावर):
  • NIFTY 50 दिवसात −2% / −3% / −4% पेक्षा जास्त पडला
  • India VIX दिवसात +15% / +25% पेक्षा जास्त वाढला
प्रत्येक पातळीसाठी दिवसातून एकदाच alert (public/log/alerts.json मध्ये नोंद).

Draft फक्त घडलेलं सांगतो + SIP ची सामान्य माहिती; कोणताही सल्ला, अंदाज किंवा scheme चं नाव नाही.

    python scripts/fall_alert.py --url <market.json URL> --state public/log/alerts.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_telegram  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NIFTY_LEVELS = [-2.0, -3.0, -4.0]   # % — जास्त घसरण = पुढची पातळी
VIX_LEVELS = [15.0, 25.0]           # % वाढ
KEEP_DAYS = 30

SIGNATURE = ("— Pankaj Sahare, Sahare Wealth (AMFI-registered Mutual Fund Distributor, ARN-151469)\n"
             "Mutual Fund investments are subject to market risks, read all scheme related documents carefully.")


def _items(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for items in (data.get("groups") or {}).values():
        for item in items or []:
            out[item["symbol"]] = item
    return out


def crossed(value: Optional[float], levels: list[float], falling: bool) -> list[float]:
    """कोणत्या पातळ्या पार झाल्या (falling: value ≤ level; नाहीतर value ≥ level)."""
    if not isinstance(value, (int, float)):
        return []
    return [lvl for lvl in levels if (value <= lvl if falling else value >= lvl)]


def check(data: dict[str, Any], state: dict[str, Any], now: datetime) -> Optional[dict[str, Any]]:
    """नवीन alert असल्यास {keys, text}; नाहीतर None. State बदलत नाही (caller करतो)."""
    today = now.astimezone(IST).date().isoformat()
    items = _items(data)
    nifty, vix = items.get("^NSEI"), items.get("^INDIAVIX")
    sent = set(state.get("sent", {}).get(today, []))

    new_keys: list[str] = []
    nifty_move = None
    if nifty and nifty.get("asof") == today and not nifty.get("stale"):
        nifty_move = nifty.get("r1d")
        new_keys += [f"nifty{int(l)}" for l in crossed(nifty_move, NIFTY_LEVELS, True) if f"nifty{int(l)}" not in sent]
    vix_move = None
    if vix and vix.get("asof") == today and not vix.get("stale"):
        vix_move = vix.get("r1d")
        new_keys += [f"vix+{int(l)}" for l in crossed(vix_move, VIX_LEVELS, False) if f"vix+{int(l)}" not in sent]
    if not new_keys:
        return None
    return {"date": today, "keys": new_keys,
            "text": build_text(data, items, nifty_move, vix_move, now)}


def _time_label(data: dict[str, Any], now: datetime) -> str:
    try:
        updated = datetime.fromisoformat(data["updated"]).astimezone(IST)
    except (KeyError, ValueError):
        updated = now.astimezone(IST)
    return updated.strftime("%I:%M %p").lstrip("0")


def client_draft(nifty: Optional[dict], nifty_move: Optional[float], vix_move: Optional[float],
                 as_of: str) -> str:
    """Clients साठी WhatsApp draft (English, descriptive)."""
    if isinstance(nifty_move, (int, float)) and nifty_move <= NIFTY_LEVELS[0]:
        opening = (f"Dear Investor, markets are down sharply today: the NIFTY 50 is lower by "
                   f"{abs(nifty_move):.1f}% (as of {as_of}).")
    else:
        opening = f"Dear Investor, market volatility has risen sharply today (as of {as_of})."
    return "\n".join([
        opening,
        "Short-term falls like this are a normal part of equity investing and have happened many times before.",
        "If you invest through SIPs, each instalment buys more units when prices are lower.",
        "We'd suggest not making changes based on a single day's movement. "
        "If you'd like to review your goals or have any questions, just reply to this message.",
        "",
        SIGNATURE,
    ])


def build_text(data: dict[str, Any], items: dict[str, dict], nifty_move: Optional[float],
               vix_move: Optional[float], now: datetime) -> str:
    as_of = _time_label(data, now)
    nifty, vix = items.get("^NSEI"), items.get("^INDIAVIX")
    lines = [f"⚠️ Market alert — {now.astimezone(IST).strftime('%d %b %Y')}, data as of {as_of} IST"]
    if nifty and isinstance(nifty_move, (int, float)):
        lines.append(f"NIFTY 50: {nifty_move:+.2f}% ({nifty.get('last', 0):,.2f})")
    if vix and isinstance(vix_move, (int, float)):
        lines.append(f"India VIX: {vix.get('last', 0):.2f} ({vix_move:+.2f}%)")
    sectors = sorted((i for i in (data.get("groups") or {}).get("sectors", []) if isinstance(i.get("r1d"), (int, float))),
                     key=lambda i: i["r1d"])[:3]
    if sectors:
        lines.append("Weakest sectors: " + ", ".join(f"{s['name']} {s['r1d']:+.2f}%" for s in sectors))
    lines += ["", "Draft for clients (review before sending):", "------",
              client_draft(nifty, nifty_move, vix_move, as_of), "------"]
    return "\n".join(lines)


def load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sent": {}}


def save_state(path: Path, state: dict[str, Any], today: str) -> None:
    keep = sorted(state.get("sent", {}))[-KEEP_DAYS:]
    state["sent"] = {d: state["sent"][d] for d in keep}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Market fall alert")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        data = json.loads(args.file.read_text(encoding="utf-8"))
    else:
        bust = int(datetime.now(timezone.utc).timestamp() // 60)
        with urllib.request.urlopen(f"{args.url}?b={bust}", timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

    now = datetime.now(timezone.utc)
    state = load_state(args.state)
    alert = check(data, state, now)
    if alert is None:
        print("No new alert")
        return 0
    print(alert["text"])
    if args.dry_run:
        return 0
    if send_telegram(alert["text"]):
        # पाठवलं तरच नोंद — fail झाल्यास पुढच्या run मध्ये पुन्हा प्रयत्न
        sent = state.setdefault("sent", {}).setdefault(alert["date"], [])
        # पुढची पातळी पार झाली तर खालच्या पातळ्याही "पाठवल्या" म्हणून
        sent.extend(k for k in alert["keys"] if k not in sent)
        save_state(args.state, state, alert["date"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
