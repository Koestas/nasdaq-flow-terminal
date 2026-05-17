"""ICT / Smart Money Concepts detection engine."""
from datetime import datetime, timedelta
from typing import Optional
import pytz

NY_TZ = pytz.timezone("America/New_York")


def is_ny_killzone() -> bool:
    now = datetime.now(NY_TZ)
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= m <= 11 * 60 + 30


def get_session_context() -> dict:
    now = datetime.now(NY_TZ)
    m = now.hour * 60 + now.minute
    wday = now.weekday()

    if wday >= 5:
        session = "Weekend"
    elif m < 9 * 60 + 30:
        if m < 4 * 60:
            session = "Asia Session"
        elif m < 8 * 60:
            session = "London Session"
        else:
            session = "Pre-Market / London Close"
    elif m <= 9 * 60 + 45:
        session = "Opening Range (first 15m)"
    elif m <= 11 * 60 + 30:
        session = "NY Killzone — Active"
    elif m <= 13 * 60:
        session = "Midday / Lunch Chop"
    elif m <= 15 * 60:
        session = "Afternoon"
    elif m <= 15 * 60 + 45:
        session = "Power Hour"
    elif m <= 16 * 60:
        session = "Final 15 Minutes"
    else:
        session = "After Hours"

    return {
        "session": session,
        "in_killzone": is_ny_killzone(),
        "time_et": now.strftime("%I:%M %p ET"),
        "day": now.strftime("%A"),
        "session_note": _session_note(session),
        "ideal_trading": is_ny_killzone() and wday < 5,
    }


def _session_note(session: str) -> str:
    return {
        "Opening Range (first 15m)": "High volatility — wait for range to form before entering.",
        "NY Killzone — Active": "Prime window. Look for sweeps, iFVG entries, VWAP reclaims.",
        "Midday / Lunch Chop": "Low-quality signals. Avoid or reduce size.",
        "Power Hour": "Trend resumes possible. Watch for PM setups.",
        "Final 15 Minutes": "Avoid new entries. Manage open positions only.",
        "Pre-Market / London Close": "Note pre-market H/L as key intraday levels.",
        "Asia Session": "Accumulation. Note Asia H/L for London/NY sweep targets.",
        "London Session": "London distributes — sweeps common. Look for reversal clues.",
        "After Hours": "Market closed. Review session and journal.",
        "Weekend": "Market closed.",
    }.get(session, "")


def extract_session_levels(bars: list) -> dict:
    if not bars:
        return {}

    today_et = datetime.now(NY_TZ).date()
    yesterday_et = today_et - timedelta(days=1)
    if today_et.weekday() == 0:
        yesterday_et = today_et - timedelta(days=3)

    asia_highs, asia_lows = [], []
    london_highs, london_lows = [], []
    premarket_highs, premarket_lows = [], []
    prev_day_bars = []
    today_bars = []

    for b in bars:
        t_raw = b.get("time", "")
        try:
            if t_raw.endswith("Z"):
                t_raw = t_raw[:-1] + "+00:00"
            dt_utc = datetime.fromisoformat(t_raw)
            dt_et = dt_utc.astimezone(NY_TZ)
        except Exception:
            continue

        h = b.get("high")
        l = b.get("low")
        if h is None or l is None:
            continue

        bar_date = dt_et.date()
        bar_m = dt_et.hour * 60 + dt_et.minute

        if bar_date == yesterday_et and 9 * 60 + 30 <= bar_m <= 16 * 60:
            prev_day_bars.append(b)
        if bar_date == today_et:
            today_bars.append(b)
        if (bar_date == yesterday_et and bar_m >= 19 * 60) or \
           (bar_date == today_et and bar_m < 3 * 60):
            asia_highs.append(h); asia_lows.append(l)
        if bar_date == today_et and 3 * 60 <= bar_m < 8 * 60:
            london_highs.append(h); london_lows.append(l)
        if bar_date == today_et and 4 * 60 <= bar_m < 9 * 60 + 30:
            premarket_highs.append(h); premarket_lows.append(l)

    result = {}
    if asia_highs:
        result["asia_high"] = round(max(asia_highs), 2)
        result["asia_low"] = round(min(asia_lows), 2)
    if london_highs:
        result["london_high"] = round(max(london_highs), 2)
        result["london_low"] = round(min(london_lows), 2)
    if premarket_highs:
        result["premarket_high"] = round(max(premarket_highs), 2)
        result["premarket_low"] = round(min(premarket_lows), 2)
    if prev_day_bars:
        opens = [b.get("open") for b in prev_day_bars if b.get("open")]
        closes = [b.get("close") for b in prev_day_bars if b.get("close")]
        highs = [b.get("high") for b in prev_day_bars if b.get("high")]
        lows = [b.get("low") for b in prev_day_bars if b.get("low")]
        if opens and closes and highs and lows:
            result["prev_day_open"] = round(opens[0], 2)
            result["prev_day_close"] = round(closes[-1], 2)
            result["prev_day_high"] = round(max(highs), 2)
            result["prev_day_low"] = round(min(lows), 2)
            pd_range = max(highs) - min(lows)
            result["prev_day_mid"] = round(min(lows) + pd_range / 2, 2)
    if today_bars:
        t_highs = [b.get("high") for b in today_bars if b.get("high")]
        t_lows = [b.get("low") for b in today_bars if b.get("low")]
        t_closes = [b.get("close") for b in today_bars if b.get("close")]
        if t_highs and t_lows:
            result["today_high"] = round(max(t_highs), 2)
            result["today_low"] = round(min(t_lows), 2)
            if t_closes:
                result["current_price"] = round(t_closes[-1], 2)
    # Fallback: use last available close (e.g. weekends / after-hours)
    if not result.get("current_price"):
        for b in reversed(bars):
            if b.get("close"):
                result["current_price"] = round(b["close"], 2)
                break
    return result


def detect_fvg(bars: list) -> list:
    fvgs = []
    n = len(bars)
    for i in range(1, n - 1):
        prev = bars[i - 1]
        curr = bars[i]
        nxt = bars[i + 1]
        if None in (prev.get("high"), prev.get("low"), nxt.get("high"), nxt.get("low")):
            continue

        is_bullish = prev["high"] < nxt["low"]
        is_bearish = prev["low"] > nxt["high"]
        if not (is_bullish or is_bearish):
            continue

        if is_bullish:
            top, bottom, fvg_type = nxt["low"], prev["high"], "bullish_fvg"
        else:
            top, bottom, fvg_type = prev["low"], nxt["high"], "bearish_fvg"

        mid = (top + bottom) / 2
        size = top - bottom
        filled = False
        inverted = False

        for j in range(i + 2, min(i + 50, n)):
            fb = bars[j]
            if fb.get("low") is None or fb.get("high") is None:
                continue
            price_in_gap = (fb["low"] <= mid <= fb["high"] or
                            (bottom <= fb["low"] <= top) or
                            (bottom <= fb["high"] <= top))
            if price_in_gap:
                filled = True
                if j + 1 < n:
                    nb = bars[j + 1]
                    if is_bullish and nb.get("close") and nb["close"] > top:
                        inverted = True; break
                    elif not is_bullish and nb.get("close") and nb["close"] < bottom:
                        inverted = True; break
                break

        fvgs.append({
            "type": "ifvg" if inverted else fvg_type,
            "base_type": fvg_type,
            "top": round(top, 2),
            "bottom": round(bottom, 2),
            "mid": round(mid, 2),
            "size": round(size, 2),
            "time": curr.get("time"),
            "filled": filled,
            "inverted": inverted,
            "strength": "strong" if size > 0.5 else "normal",
            "description": _fvg_desc(fvg_type, top, bottom, inverted),
        })
    return fvgs[-20:]


def _fvg_desc(fvg_type, top, bottom, inverted):
    d = "Bullish" if fvg_type == "bullish_fvg" else "Bearish"
    if inverted:
        role = "support" if fvg_type == "bullish_fvg" else "resistance"
        return f"iFVG ({d}) {bottom:.2f}–{top:.2f}: inverted — now acts as {role}"
    return f"FVG ({d}) {bottom:.2f}–{top:.2f}: price may return to fill"


def detect_order_block(bars: list) -> list:
    if len(bars) < 5:
        return []
    ranges = [abs((b.get("high") or 0) - (b.get("low") or 0)) for b in bars]
    avg_range = sum(ranges) / len(ranges) if ranges else 0.01
    obs = []
    for i in range(2, len(bars) - 3):
        b, b1, b2 = bars[i], bars[i+1], bars[i+2]
        if None in (b.get("close"), b.get("open"), b1.get("close"), b2.get("close")):
            continue
        bull = (b1["close"] > b1.get("open", b1["close"]) and
                b2["close"] > b2.get("open", b2["close"]) and
                (b2["close"] - b1.get("open", b1["close"])) > avg_range * 1.5)
        if bull and b["close"] < b.get("open", b["close"]):
            obs.append({"type": "bullish_ob", "high": round(b.get("high", 0), 2),
                        "low": round(b.get("low", 0), 2),
                        "mid": round((b.get("high", 0) + b.get("low", 0)) / 2, 2),
                        "time": b.get("time"),
                        "description": f"Bullish OB {b.get('low',0):.2f}–{b.get('high',0):.2f}: demand zone"})
        bear = (b1["close"] < b1.get("open", b1["close"]) and
                b2["close"] < b2.get("open", b2["close"]) and
                (b1.get("open", b1["close"]) - b2["close"]) > avg_range * 1.5)
        if bear and b["close"] > b.get("open", b["close"]):
            obs.append({"type": "bearish_ob", "high": round(b.get("high", 0), 2),
                        "low": round(b.get("low", 0), 2),
                        "mid": round((b.get("high", 0) + b.get("low", 0)) / 2, 2),
                        "time": b.get("time"),
                        "description": f"Bearish OB {b.get('low',0):.2f}–{b.get('high',0):.2f}: supply zone"})
    return obs[-10:]


def detect_equal_highs_lows(bars: list, tolerance_pct: float = 0.05) -> dict:
    if len(bars) < 10:
        return {"equal_highs": [], "equal_lows": []}

    def find_equals(pivots, is_high):
        result, used = [], set()
        for i in range(len(pivots)):
            if i in used: continue
            idx_i, val_i = pivots[i]
            tol = val_i * tolerance_pct / 100
            group = [(idx_i, val_i)]
            for j in range(i + 1, len(pivots)):
                if j in used: continue
                idx_j, val_j = pivots[j]
                if abs(val_j - val_i) <= tol:
                    group.append((idx_j, val_j)); used.add(j)
            if len(group) >= 2:
                avg = sum(v for _, v in group) / len(group)
                result.append({"level": round(avg, 2), "count": len(group),
                               "type": "equal_highs" if is_high else "equal_lows",
                               "description": f"{'Equal Highs' if is_high else 'Equal Lows'} at {avg:.2f} — liquidity pool",
                               "times": [bars[idx].get("time") for idx, _ in group if idx < len(bars)]})
                used.add(i)
        return sorted(result, key=lambda x: x["count"], reverse=True)[:5]

    highs = [(i, b.get("high")) for i, b in enumerate(bars) if b.get("high")]
    lows = [(i, b.get("low")) for i, b in enumerate(bars) if b.get("low")]
    return {"equal_highs": find_equals(highs, True), "equal_lows": find_equals(lows, False)}


def calc_discount_premium(session_levels: dict, current_price: Optional[float]) -> dict:
    day_high = session_levels.get("today_high") or session_levels.get("prev_day_high")
    day_low = session_levels.get("today_low") or session_levels.get("prev_day_low")
    if not day_high or not day_low or not current_price:
        return {"zone": "unknown", "equilibrium": None, "position_pct": None}
    total_range = day_high - day_low
    if total_range <= 0:
        return {"zone": "unknown", "equilibrium": None, "position_pct": None}
    eq = round(day_low + total_range / 2, 2)
    pos_pct = round((current_price - day_low) / total_range * 100, 1)
    zone = "discount" if pos_pct <= 50 else "premium"
    return {
        "zone": zone,
        "zone_note": "Price in discount — look for longs / bullish setups" if zone == "discount" else "Price in premium — look for shorts / bearish setups",
        "equilibrium": eq, "day_high": day_high, "day_low": day_low, "position_pct": pos_pct,
    }


def identify_draw_on_liquidity(session_levels: dict, equal_hl: dict, current_price: Optional[float]) -> dict:
    if not current_price:
        return {"target": None, "direction": None, "reason": None}
    above, below = [], []
    for eh in equal_hl.get("equal_highs", []):
        if eh["level"] > current_price:
            above.append({"level": eh["level"], "reason": f"Equal Highs at {eh['level']:.2f}"})
    for el in equal_hl.get("equal_lows", []):
        if el["level"] < current_price:
            below.append({"level": el["level"], "reason": f"Equal Lows at {el['level']:.2f}"})
    for key, label in [("asia_high","Asia High"),("london_high","London High"),("today_high","Today's High"),("prev_day_high","Prev Day High")]:
        v = session_levels.get(key)
        if v and v > current_price: above.append({"level": v, "reason": f"{label} at {v:.2f}"})
    for key, label in [("asia_low","Asia Low"),("london_low","London Low"),("today_low","Today's Low"),("prev_day_low","Prev Day Low")]:
        v = session_levels.get(key)
        if v and v < current_price: below.append({"level": v, "reason": f"{label} at {v:.2f}"})
    na = min(above, key=lambda x: x["level"] - current_price, default=None) if above else None
    nb = min(below, key=lambda x: current_price - x["level"], default=None) if below else None
    if na and nb:
        du, dd = na["level"] - current_price, current_price - nb["level"]
        if du < dd * 0.7: return {"target": na["level"], "direction": "up", "reason": na["reason"]}
        if dd < du * 0.7: return {"target": nb["level"], "direction": "down", "reason": nb["reason"]}
        return {"target": None, "direction": "neutral", "reason": "Equal distance to targets above and below"}
    if na: return {"target": na["level"], "direction": "up", "reason": na["reason"]}
    if nb: return {"target": nb["level"], "direction": "down", "reason": nb["reason"]}
    return {"target": None, "direction": "neutral", "reason": "No clear liquidity target identified"}


def score_setup(in_killzone, has_ifvg, in_discount_for_long, draw_aligned, has_order_block, vwap_aligned) -> dict:
    items = [
        ("NY Killzone active", in_killzone, 25),
        ("iFVG present for entry", has_ifvg, 25),
        ("Price in discount/premium zone", in_discount_for_long, 20),
        ("Draw on liquidity aligned", draw_aligned, 20),
        ("Order block confluence", has_order_block, 5),
        ("VWAP aligned", vwap_aligned, 5),
    ]
    score = sum(pts for _, met, pts in items if met)
    checklist = [{"item": name, "met": met} for name, met, _ in items]
    grade = "A+" if score >= 80 else "A" if score >= 60 else "B" if score >= 40 else "C"
    return {"score": score, "grade": grade, "checklist": checklist}


def get_ict_analysis(bars: list, vwap: Optional[float] = None, current_price: Optional[float] = None) -> dict:
    session = get_session_context()
    fvgs = detect_fvg(bars)
    obs = detect_order_block(bars)
    session_levels = extract_session_levels(bars)
    equal_hl = detect_equal_highs_lows(bars)
    price = current_price or session_levels.get("current_price")
    dp = calc_discount_premium(session_levels, price)
    draw = identify_draw_on_liquidity(session_levels, equal_hl, price)
    ifvgs = [f for f in fvgs if f.get("inverted")]
    bullish_fvgs = [f for f in fvgs if f["base_type"] == "bullish_fvg" and not f["filled"]]
    bearish_fvgs = [f for f in fvgs if f["base_type"] == "bearish_fvg" and not f["filled"]]
    in_disc = dp.get("zone") == "discount"
    vwap_bull = vwap is not None and price is not None and price > vwap
    vwap_bear = vwap is not None and price is not None and price < vwap
    long_setup = score_setup(session["in_killzone"], any(f["base_type"]=="bullish_fvg" for f in ifvgs),
                             in_disc, draw.get("direction")=="up",
                             any(o["type"]=="bullish_ob" for o in obs), vwap_bull)
    short_setup = score_setup(session["in_killzone"], any(f["base_type"]=="bearish_fvg" for f in ifvgs),
                              not in_disc, draw.get("direction")=="down",
                              any(o["type"]=="bearish_ob" for o in obs), vwap_bear)
    return {
        "session": session, "session_levels": session_levels, "discount_premium": dp,
        "draw_on_liquidity": draw, "fair_value_gaps": fvgs, "ifvgs": ifvgs,
        "order_blocks": obs, "equal_highs_lows": equal_hl,
        "long_setup": long_setup, "short_setup": short_setup,
        "summary": {"total_fvgs": len(fvgs), "unfilled_bullish_fvgs": len(bullish_fvgs),
                    "unfilled_bearish_fvgs": len(bearish_fvgs), "ifvg_count": len(ifvgs), "total_obs": len(obs)},
    }
