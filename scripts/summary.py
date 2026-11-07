"""
"What moved" summary: market.json च्या groups वरून 3–6 English वाक्यं.
  • S2 (daily)  — build_summary(groups)          → 1-day moves
  • S5 (weekly) — build_weekly_summary(groups)   → 1-week moves (Weekly Market Recap)
फक्त घडलेल्या घटना (descriptive) — कोणताही अंदाज, सल्ला किंवा "buy/sell" शब्द नाही.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

Item = dict[str, Any]

REGION_ORDER = ["India", "US", "Europe", "Asia"]
REGION_NAMES = {"US": "Wall Street", "Europe": "European markets", "Asia": "Asian markets"}
MAX_LINES = 6


@dataclass(frozen=True)
class Period:
    field: str          # कोणता return: r1d / r1w
    suffix: str         # वाक्यात कालावधी, उदा. " this week"
    big_move: float     # region "rallied"/"fell sharply" सीमा (%)
    small_move: float   # region "rose"/"fell" सीमा (%)
    leader: float       # "led by" दाखवण्याची सीमा (%)
    vix: float
    brent: float
    inr: float
    gold: float


DAILY = Period("r1d", "", 1.0, 0.25, 1.0, 5.0, 2.0, 0.3, 1.5)
WEEKLY = Period("r1w", " this week", 2.0, 0.5, 2.0, 10.0, 4.0, 0.5, 2.5)


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pct(v: float) -> str:
    return f"{v:+.2f}%"


def _fmt(v: float, digits: int = 2) -> str:
    return f"{v:,.{digits}f}"


def _fresh(items: list[Item], field: str) -> list[Item]:
    return [i for i in items if not i.get("stale") and _num(i.get(field))]


def _verb(avg: float, p: Period) -> str:
    if avg >= p.big_move:
        return "rallied"
    if avg >= p.small_move:
        return "rose"
    if avg <= -p.big_move:
        return "fell sharply"
    if avg <= -p.small_move:
        return "fell"
    return "mixed"


def _india_line(globals_: list[Item], p: Period) -> Optional[str]:
    by_symbol = {g["symbol"]: g for g in globals_}
    nifty, sensex = by_symbol.get("^NSEI"), by_symbol.get("^BSESN")
    if not nifty:
        return None
    move = nifty[p.field]
    word = "rose" if move > 0 else "fell" if move < 0 else "was unchanged"
    line = f"NIFTY 50 {word} {abs(move):.2f}%{p.suffix} to {_fmt(nifty['last'])}"
    if sensex:
        line += f", while the Sensex moved {_pct(sensex[p.field])}"
    return line + "."


def _region_line(region: str, items: list[Item], p: Period) -> Optional[str]:
    if not items:
        return None
    avg = sum(i[p.field] for i in items) / len(items)
    name = REGION_NAMES.get(region, region)
    leader = max(items, key=lambda i: abs(i[p.field]))
    be = "were" if name.endswith("markets") else "was"
    verb = _verb(avg, p)
    if verb == "mixed":
        if len(items) >= 3:
            moves = ", ".join(f"{i['name']} {_pct(i[p.field])}" for i in items)
            return f"{name} {be} mixed{p.suffix}: {moves}."
        verb = f"{be} mixed"
    line = f"{name} {verb}{p.suffix}"
    if abs(leader[p.field]) >= p.leader:
        line += f", led by {leader['name']} ({_pct(leader[p.field])})"
    else:
        line += f" (average {_pct(avg)})"
    return line + "."


def _sector_line(sectors: list[Item], p: Period) -> Optional[str]:
    if len(sectors) < 3:
        return None
    ranked = sorted(sectors, key=lambda i: i[p.field], reverse=True)
    best, worst = ranked[0], ranked[-1]
    return (f"Among Indian sectors{p.suffix}, {best['name']} led ({_pct(best[p.field])}) "
            f"and {worst['name']} lagged ({_pct(worst[p.field])}).")


def _risk_lines(risk: list[Item], p: Period) -> list[str]:
    by_symbol = {i["symbol"]: i for i in risk}
    lines: list[str] = []
    vix = by_symbol.get("^VIX")
    if vix and abs(vix[p.field]) >= p.vix:
        word = "jumped" if vix[p.field] > 0 else "eased"
        lines.append(f"The US volatility index (VIX) {word} {abs(vix[p.field]):.2f}%{p.suffix} to {_fmt(vix['last'])}.")
    brent = by_symbol.get("BZ=F")
    if brent and abs(brent[p.field]) >= p.brent:
        word = "rose" if brent[p.field] > 0 else "fell"
        lines.append(f"Brent crude {word} {abs(brent[p.field]):.2f}%{p.suffix} to ${_fmt(brent['last'])} a barrel.")
    inr = by_symbol.get("INR=X")
    if inr and abs(inr[p.field]) >= p.inr:
        # USD/INR खाली = rupee मजबूत
        word = "strengthened" if inr[p.field] < 0 else "weakened"
        lines.append(f"The rupee {word} against the US dollar{p.suffix} (USD/INR {_fmt(inr['last'])}).")
    gold = by_symbol.get("GC=F")
    if gold and abs(gold[p.field]) >= p.gold:
        word = "rose" if gold[p.field] > 0 else "fell"
        lines.append(f"Gold {word} {abs(gold[p.field]):.2f}%{p.suffix}.")
    return lines


def _build(groups: dict[str, list[Item]], p: Period) -> list[str]:
    globals_ = _fresh(groups.get("global") or [], p.field)
    lines: list[str] = []
    india = _india_line(globals_, p)
    if india:
        lines.append(india)
    for region in REGION_ORDER[1:]:
        line = _region_line(region, [g for g in globals_ if g.get("region") == region], p)
        if line:
            lines.append(line)
    sector = _sector_line(_fresh(groups.get("sectors") or [], p.field), p)
    if sector:
        lines.append(sector)
    lines.extend(_risk_lines(_fresh(groups.get("risk") or [], p.field), p))
    return lines[:MAX_LINES]


def build_summary(groups: dict[str, list[Item]]) -> list[str]:
    """S2: आजचे moves."""
    return _build(groups, DAILY)


def build_weekly_summary(groups: dict[str, list[Item]]) -> list[str]:
    """S5: आठवड्याचे moves (Weekly Market Recap)."""
    return _build(groups, WEEKLY)
