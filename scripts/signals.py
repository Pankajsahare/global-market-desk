"""
India-open cue आणि Risk mood — public/widget/gmd.js मधल्या JS rules ची Python प्रत.
⚠️ Rules बदलल्यास दोन्ही ठिकाणी बदला (tests/test_signals.py parity तपासतो).
   invest-core मध्ये core/cue_rules.py ही याचीच हुबेहूब प्रत आहे (S4 weekly report फरक दिसल्यास सांगतो).
"""
from __future__ import annotations

from typing import Any, Optional

Item = dict[str, Any]

# label, weight, symbols, invert (वाढ = नकारात्मक)
CUE_COMPONENTS = [
    ("US close", 0.30, ["^GSPC", "^IXIC", "^DJI"], False),
    ("Asia now", 0.30, ["^N225", "^HSI", "000001.SS", "^KS11"], False),
    ("US futures", 0.20, ["ES=F", "NQ=F"], False),
    ("USD/INR", 0.10, ["INR=X"], True),
    ("Brent crude", 0.10, ["BZ=F"], True),
]


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _avg(values: list[Any]) -> Optional[float]:
    xs = [v for v in values if _num(v)]
    return sum(xs) / len(xs) if xs else None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def index_items(data: dict[str, Any]) -> tuple[dict[str, Item], list[Item]]:
    """market.json → ({symbol: item}, global items)."""
    groups = data.get("groups") or {}
    mapping: dict[str, Item] = {}
    for items in groups.values():
        for item in items or []:
            mapping[item["symbol"]] = item
    return mapping, list(groups.get("global") or [])


def compute_cue(mapping: dict[str, Item]) -> dict[str, Any]:
    total = used = 0.0
    rows = []
    for label, weight, symbols, invert in CUE_COMPONENTS:
        move = _avg([mapping[s].get("r1d") if s in mapping else None for s in symbols])
        if move is None:
            rows.append({"label": label, "weight": weight, "move": None, "impact": None})
            continue
        signal = _clamp(-move if invert else move, -2, 2)
        total += signal * weight
        used += weight
        rows.append({"label": label, "weight": weight, "move": move, "impact": signal * weight})
    score = total / used if used else 0.0  # डेटा कमी असल्यास re-normalise
    if score >= 0.5:
        text = "Positive"
    elif score >= 0.15:
        text = "Mildly Positive"
    elif score <= -0.5:
        text = "Negative"
    elif score <= -0.15:
        text = "Mildly Negative"
    else:
        text = "Flat"
    return {"score": score, "label": text, "rows": rows, "coverage": used}


def _yield(v: float, ref: float) -> float:
    # Yahoo कधी 42.5 (×10) तर कधी 4.25 देतो
    return v / 10 if ref > 20 else v


def compute_mood(mapping: dict[str, Item], globals_: list[Item]) -> dict[str, Any]:
    score = 50
    reasons: list[tuple[int, str]] = []

    def add(points: int, text: str) -> None:
        nonlocal score
        score += points
        reasons.append((points, text))

    vix = mapping.get("^VIX")
    if vix and _num(vix.get("last")):
        v = vix["last"]
        if v < 16:
            add(10, f"CBOE VIX at {v:.1f} (below 16): calm US market")
        elif v > 22:
            add(-15, f"CBOE VIX at {v:.1f} (above 22): fear rising")
        else:
            add(0, f"CBOE VIX at {v:.1f}: neutral zone")

    ivix = mapping.get("^INDIAVIX")
    if ivix and _num(ivix.get("last")):
        v = ivix["last"]
        if v < 13:
            add(5, f"India VIX at {v:.1f} (below 13): low volatility")
        elif v > 18:
            add(-10, f"India VIX at {v:.1f} (above 18): high volatility")
        else:
            add(0, f"India VIX at {v:.1f}: normal")

    dxy = mapping.get("DX-Y.NYB")
    if dxy and _num(dxy.get("r1w")):
        w = dxy["r1w"]
        if w > 1:
            add(-10, f"Dollar Index up {w:.2f}% in 1W: pressure on emerging markets")
        elif w < -1:
            add(5, f"Dollar Index down {abs(w):.2f}% in 1W: supportive for emerging markets")
        else:
            add(0, f"Dollar Index stable in 1W ({w:.2f}%)")

    tnx = mapping.get("^TNX")
    if tnx and _num(tnx.get("d1w")) and _num(tnx.get("last")):
        dy = _yield(tnx["d1w"], tnx["last"])
        y = _yield(tnx["last"], tnx["last"])
        if dy > 0.10:
            add(-10, f"US 10Y yield up {dy:.2f} pts in 1W to {y:.2f}%")
        elif dy < -0.10:
            add(5, f"US 10Y yield down {abs(dy):.2f} pts in 1W to {y:.2f}%")
        else:
            add(0, f"US 10Y yield steady at {y:.2f}%")

    brent = mapping.get("BZ=F")
    if brent and _num(brent.get("r1w")):
        w = brent["r1w"]
        if w > 5:
            add(-10, f"Brent up {w:.2f}% in 1W: negative for India")
        elif w < -5:
            add(5, f"Brent down {abs(w):.2f}% in 1W: positive for India")
        else:
            add(0, f"Brent move in 1W: {w:.2f}%")

    gold = mapping.get("GC=F")
    world_week = _avg([g.get("r1w") for g in globals_])
    if gold and _num(gold.get("r1w")) and world_week is not None and gold["r1w"] > 2 and world_week < 0:
        add(-5, f"Gold up {gold['r1w']:.2f}% while world equities fell in 1W: safe-haven demand")

    moving = [g for g in globals_ if _num(g.get("r1d"))]
    if moving:
        up_share = sum(1 for g in moving if g["r1d"] > 0) / len(moving)
        text = f"{round(up_share * 100)}% of world indices up today"
        if up_share > 0.66:
            add(10, text + ": broad strength")
        elif up_share < 0.33:
            add(-10, text + ": broad weakness")
        else:
            add(0, text + ": mixed")

    # JS Math.round सारखं (.5 वर वर) — Python round() banker's rounding करतो
    score = int(_clamp(int(score + 0.5) if score >= 0 else -int(-score + 0.5), 0, 100))
    label = "Risk-On" if score >= 60 else "Risk-Off" if score <= 40 else "Neutral"
    return {"score": score, "label": label, "reasons": reasons}
