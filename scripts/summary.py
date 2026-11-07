"""
S2 — "What moved" summary: market.json च्या groups वरून 3–6 English वाक्यं.
फक्त घडलेल्या घटना (descriptive) — कोणताही अंदाज, सल्ला किंवा "buy/sell" शब्द नाही.
"""
from __future__ import annotations

from typing import Any, Optional

Item = dict[str, Any]

REGION_ORDER = ["India", "US", "Europe", "Asia"]
REGION_NAMES = {"US": "Wall Street", "Europe": "European markets", "Asia": "Asian markets"}
MAX_LINES = 6


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pct(v: float) -> str:
    return f"{v:+.2f}%"


def _fmt(v: float, digits: int = 2) -> str:
    return f"{v:,.{digits}f}"


def _fresh(items: list[Item]) -> list[Item]:
    return [i for i in items if not i.get("stale") and _num(i.get("r1d"))]


def _verb(avg: float) -> str:
    if avg >= 1:
        return "rallied"
    if avg >= 0.25:
        return "rose"
    if avg <= -1:
        return "fell sharply"
    if avg <= -0.25:
        return "fell"
    return "mixed"


def _india_line(globals_: list[Item]) -> Optional[str]:
    by_symbol = {g["symbol"]: g for g in globals_}
    nifty, sensex = by_symbol.get("^NSEI"), by_symbol.get("^BSESN")
    if not nifty:
        return None
    word = "rose" if nifty["r1d"] > 0 else "fell" if nifty["r1d"] < 0 else "was unchanged"
    line = f"NIFTY 50 {word} {abs(nifty['r1d']):.2f}% to {_fmt(nifty['last'])}"
    if sensex:
        line += f", while the Sensex moved {_pct(sensex['r1d'])}"
    return line + "."


def _region_line(region: str, items: list[Item]) -> Optional[str]:
    if not items:
        return None
    avg = sum(i["r1d"] for i in items) / len(items)
    name = REGION_NAMES.get(region, region)
    leader = max(items, key=lambda i: abs(i["r1d"]))
    be = "were" if name.endswith("markets") else "was"
    verb = _verb(avg)
    if verb == "mixed":
        if len(items) >= 3:
            moves = ", ".join(f"{i['name']} {_pct(i['r1d'])}" for i in items)
            return f"{name} {be} mixed: {moves}."
        verb = f"{be} mixed"
    line = f"{name} {verb}"
    if abs(leader["r1d"]) >= 1:
        line += f", led by {leader['name']} ({_pct(leader['r1d'])})"
    else:
        line += f" (average {_pct(avg)})"
    return line + "."


def _sector_line(sectors: list[Item]) -> Optional[str]:
    if len(sectors) < 3:
        return None
    ranked = sorted(sectors, key=lambda i: i["r1d"], reverse=True)
    best, worst = ranked[0], ranked[-1]
    return (f"Among Indian sectors, {best['name']} led ({_pct(best['r1d'])}) "
            f"and {worst['name']} lagged ({_pct(worst['r1d'])}).")


def _risk_lines(risk: list[Item]) -> list[str]:
    by_symbol = {i["symbol"]: i for i in risk}
    lines: list[str] = []
    vix = by_symbol.get("^VIX")
    if vix and abs(vix["r1d"]) >= 5:
        word = "jumped" if vix["r1d"] > 0 else "eased"
        lines.append(f"The US volatility index (VIX) {word} {abs(vix['r1d']):.2f}% to {_fmt(vix['last'])}.")
    brent = by_symbol.get("BZ=F")
    if brent and abs(brent["r1d"]) >= 2:
        word = "rose" if brent["r1d"] > 0 else "fell"
        lines.append(f"Brent crude {word} {abs(brent['r1d']):.2f}% to ${_fmt(brent['last'])} a barrel.")
    inr = by_symbol.get("INR=X")
    if inr and abs(inr["r1d"]) >= 0.3:
        # USD/INR खाली = rupee मजबूत
        word = "strengthened" if inr["r1d"] < 0 else "weakened"
        lines.append(f"The rupee {word} against the US dollar (USD/INR {_fmt(inr['last'])}).")
    gold = by_symbol.get("GC=F")
    if gold and abs(gold["r1d"]) >= 1.5:
        word = "rose" if gold["r1d"] > 0 else "fell"
        lines.append(f"Gold {word} {abs(gold['r1d']):.2f}%.")
    return lines


def build_summary(groups: dict[str, list[Item]]) -> list[str]:
    """Groups → वाक्यांची यादी (जास्तीत जास्त MAX_LINES)."""
    globals_ = _fresh(groups.get("global") or [])
    lines: list[str] = []

    india = _india_line(globals_)
    if india:
        lines.append(india)
    for region in REGION_ORDER[1:]:
        line = _region_line(region, [g for g in globals_ if g.get("region") == region])
        if line:
            lines.append(line)
    sector = _sector_line(_fresh(groups.get("sectors") or []))
    if sector:
        lines.append(sector)
    lines.extend(_risk_lines(_fresh(groups.get("risk") or [])))
    return lines[:MAX_LINES]
