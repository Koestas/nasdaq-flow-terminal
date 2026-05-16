"""Options flow statistics calculations."""
import math
from typing import Optional


def clean(val):
    if val is None:
        return None
    try:
        if math.isnan(val) or math.isinf(val):
            return None
    except TypeError:
        pass
    return val


def calc_wave(calls: list, puts: list) -> dict:
    """Calculate WAVE metrics from options chain."""
    call_premium = sum((c.get("estimated_premium") or 0) for c in calls)
    put_premium = sum((p.get("estimated_premium") or 0) for p in puts)
    net_wave = call_premium - put_premium
    total = call_premium + put_premium
    cp_ratio = call_premium / put_premium if put_premium > 0 else None
    pc_ratio = put_premium / call_premium if call_premium > 0 else None
    call_dominance_pct = (call_premium / total * 100) if total > 0 else 50.0
    return {
        "call_wave": clean(call_premium),
        "put_wave": clean(put_premium),
        "net_wave": clean(net_wave),
        "total_premium": clean(total),
        "call_put_ratio": clean(cp_ratio),
        "put_call_ratio": clean(pc_ratio),
        "call_dominance_pct": clean(call_dominance_pct),
        "wave_direction": "bullish" if net_wave > 0 else ("bearish" if net_wave < 0 else "neutral"),
    }


def calc_gex(calls: list, puts: list, spot: float) -> dict:
    """Calculate gamma exposure by strike."""
    strikes: dict = {}
    for c in calls:
        s = c.get("strike")
        if s is None:
            continue
        gex = (c.get("gex") or 0)
        strikes[s] = strikes.get(s, {"strike": s, "call_gex": 0, "put_gex": 0})
        strikes[s]["call_gex"] += gex
    for p in puts:
        s = p.get("strike")
        if s is None:
            continue
        gex = -(p.get("gex") or 0)  # put GEX is negative
        strikes[s] = strikes.get(s, {"strike": s, "call_gex": 0, "put_gex": 0})
        strikes[s]["put_gex"] += gex

    gex_list = []
    for s, v in sorted(strikes.items()):
        net = v["call_gex"] + v["put_gex"]
        gex_list.append({"strike": s, "call_gex": clean(v["call_gex"]),
                         "put_gex": clean(v["put_gex"]), "net_gex": clean(net)})

    net_total = sum(g["net_gex"] or 0 for g in gex_list)
    call_wall = _find_wall(calls, spot, above=True)
    put_wall = _find_wall(puts, spot, above=False)

    return {
        "by_strike": gex_list,
        "net_gex": clean(net_total),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "spot": spot,
    }


def _find_wall(contracts: list, spot: float, above: bool) -> Optional[float]:
    """Find the strike with highest OI above (calls) or below (puts) spot."""
    filtered = [c for c in contracts if c.get("strike") is not None and c.get("openInterest") is not None]
    if above:
        filtered = [c for c in filtered if c["strike"] > spot]
    else:
        filtered = [c for c in filtered if c["strike"] < spot]
    if not filtered:
        return None
    best = max(filtered, key=lambda c: c.get("openInterest", 0))
    return best.get("strike")


def calc_top_flow(calls: list, puts: list, top_n: int = 20) -> list:
    """Return top contracts by estimated premium."""
    all_contracts = calls + puts
    sorted_contracts = sorted(all_contracts, key=lambda c: c.get("estimated_premium") or 0, reverse=True)
    result = []
    for c in sorted_contracts[:top_n]:
        prem = c.get("estimated_premium") or 0
        vol = c.get("volume") or 0
        oi = c.get("openInterest") or 0
        result.append({
            **c,
            "side_estimate": "ask-side" if vol > oi * 0.5 else "bid-side",
            "signal": "bullish" if c.get("side") == "call" else "bearish",
            "premium_size": _premium_size(prem),
        })
    return result


def _premium_size(prem: float) -> str:
    if prem >= 5_000_000:
        return "whale"
    if prem >= 1_000_000:
        return "large"
    if prem >= 100_000:
        return "medium"
    return "small"


def calc_unusual(calls: list, puts: list) -> list:
    """Return contracts flagged as unusual."""
    unusual = [c for c in calls + puts if c.get("unusual_flag")]
    result = []
    for c in unusual:
        reasons = []
        vol = c.get("volume") or 0
        oi = c.get("openInterest") or 0
        prem = c.get("estimated_premium") or 0
        if vol > 2 * oi:
            reasons.append(f"Volume ({vol:,}) > 2x OI ({oi:,})")
        if prem > 500_000:
            reasons.append(f"Large premium ({prem/1e6:.2f}M)")
        result.append({**c, "unusual_reasons": reasons, "premium_size": _premium_size(prem)})
    result.sort(key=lambda c: c.get("estimated_premium") or 0, reverse=True)
    return result


def calc_heatmap(calls: list, puts: list) -> dict:
    """Strike heatmaps for volume, OI, premium, gamma."""
    strikes = sorted(set(
        [c["strike"] for c in calls if c.get("strike")] +
        [p["strike"] for p in puts if p.get("strike")]
    ))
    def agg(contracts, field):
        m = {}
        for c in contracts:
            s = c.get("strike")
            if s is not None:
                m[s] = m.get(s, 0) + (c.get(field) or 0)
        return [{"strike": s, "value": clean(m.get(s, 0))} for s in strikes]

    return {
        "volume": {"calls": agg(calls, "volume"), "puts": agg(puts, "volume")},
        "open_interest": {"calls": agg(calls, "openInterest"), "puts": agg(puts, "openInterest")},
        "premium": {"calls": agg(calls, "estimated_premium"), "puts": agg(puts, "estimated_premium")},
        "gamma": {"calls": agg(calls, "gamma"), "puts": agg(puts, "gamma")},
    }
