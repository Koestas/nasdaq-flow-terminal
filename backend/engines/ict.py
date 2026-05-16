"""ICT / Smart Money Concepts detection engine.
Covers: Fair Value Gaps (iFVGs), Order Blocks, NY Killzone session filter.
"""
from datetime import datetime
from typing import Optional
import pytz


NY_TZ = pytz.timezone("America/New_York")


def is_ny_killzone() -> bool:
    """True if current time is within NY morning session 9:30–11:30 AM ET."""
    now = datetime.now(NY_TZ)
    if now.weekday() >= 5:  # weekend
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 11 * 60 + 30


def get_session_context() -> dict:
    """Returns current session context for display."""
    now = datetime.now(NY_TZ)
    minutes = now.hour * 60 + now.minute
    in_killzone = is_ny_killzone()
    market_open = 9 * 60 + 30
    market_close = 16 * 60

    if now.weekday() >= 5:
        session = "Weekend"
    elif minutes < market_open:
        session = "Pre-Market"
    elif minutes <= market_open + 15:
        session = "Opening Range (first 15m)"
    elif minutes <= market_open + 60:
        session = "NY Killzone — First Hour"
    elif minutes <= 11 * 60 + 30:
        session = "NY Killzone — Active"
    elif minutes <= 13 * 60:
        session = "Midday / Lunch Chop"
    elif minutes <= market_close - 60:
        session = "Afternoon"
    elif minutes <= market_close - 15:
        session = "Power Hour"
    elif minutes <= market_close:
        session = "Final 15 Minutes"
    else:
        session = "After Hours"

    return {
        "session": session,
        "in_killzone": in_killzone,
        "time_et": now.strftime("%I:%M %p"),
        "day": now.strftime("%A"),
        "session_note": _session_note(session),
    }


def _session_note(session: str) -> str:
    notes = {
        "Opening Range (first 15m)": "High volatility — wait for range to establish before trading.",
        "NY Killzone — First Hour": "Prime trading window. Confirm VWAP + structure before entry.",
        "NY Killzone — Active": "Active killzone. Use VWAP reclaims and rejections for setups.",
        "Midday / Lunch Chop": "Low quality signals. Reduce size or avoid. Wait for PM setup.",
        "Power Hour": "Can trend again. Watch for breakouts with volume.",
        "Final 15 Minutes": "Avoid new entries. Manage open positions.",
        "Pre-Market": "Range forming. Note pre-market H/L as key levels.",
        "After Hours": "Market closed. Review session.",
        "Weekend": "Market closed.",
    }
    return notes.get(session, "")


def detect_fvg(bars: list) -> list:
    """
    Detect Fair Value Gaps (FVG / iFVG) in OHLCV bar data.

    Bullish FVG: bar[i-1].high < bar[i+1].low  (gap up — price should revisit)
    Bearish FVG: bar[i-1].low > bar[i+1].high  (gap down — price should revisit)

    bars: list of dicts with keys: time, open, high, low, close
    """
    fvgs = []
    for i in range(1, len(bars) - 1):
        prev = bars[i - 1]
        curr = bars[i]
        nxt = bars[i + 1]
        if None in (prev.get("high"), prev.get("low"), nxt.get("high"), nxt.get("low")):
            continue

        # Bullish FVG
        if prev["high"] < nxt["low"]:
            fvgs.append({
                "type": "bullish_fvg",
                "top": nxt["low"],
                "bottom": prev["high"],
                "mid": (nxt["low"] + prev["high"]) / 2,
                "time": curr.get("time"),
                "filled": False,
                "description": f"Bullish FVG {prev['high']:.2f}–{nxt['low']:.2f}: price may return to fill this gap",
            })

        # Bearish FVG
        elif prev["low"] > nxt["high"]:
            fvgs.append({
                "type": "bearish_fvg",
                "top": prev["low"],
                "bottom": nxt["high"],
                "mid": (prev["low"] + nxt["high"]) / 2,
                "time": curr.get("time"),
                "filled": False,
                "description": f"Bearish FVG {nxt['high']:.2f}–{prev['low']:.2f}: price may return to fill this gap",
            })

    return fvgs


def detect_order_block(bars: list) -> list:
    """
    Detect order blocks — the last opposing candle before a strong impulsive move.

    Bullish OB: last bearish (red) candle before a strong up move
    Bearish OB: last bullish (green) candle before a strong down move

    A "strong move" = 3 consecutive candles in the same direction with total range > 2x avg range.
    """
    if len(bars) < 5:
        return []

    ranges = [abs((b.get("high") or 0) - (b.get("low") or 0)) for b in bars]
    avg_range = sum(ranges) / len(ranges) if ranges else 0

    order_blocks = []
    for i in range(2, len(bars) - 2):
        b = bars[i]
        b1 = bars[i + 1]
        b2 = bars[i + 2]
        if None in (b.get("close"), b.get("open"), b1.get("close"), b2.get("close")):
            continue

        # Check for strong bullish impulse after bar i
        bullish_impulse = (b1["close"] > b1["open"] and b2["close"] > b2["open"]
                           and (b2["close"] - b1["open"]) > avg_range * 1.5)
        if bullish_impulse and b["close"] < b["open"]:  # last bearish candle before impulse
            order_blocks.append({
                "type": "bullish_ob",
                "high": b.get("high"),
                "low": b.get("low"),
                "time": b.get("time"),
                "description": f"Bullish OB at {b.get('low', 0):.2f}–{b.get('high', 0):.2f}: support zone",
            })

        # Check for strong bearish impulse after bar i
        bearish_impulse = (b1["close"] < b1["open"] and b2["close"] < b2["open"]
                           and (b1["open"] - b2["close"]) > avg_range * 1.5)
        if bearish_impulse and b["close"] > b["open"]:  # last bullish candle before impulse
            order_blocks.append({
                "type": "bearish_ob",
                "high": b.get("high"),
                "low": b.get("low"),
                "time": b.get("time"),
                "description": f"Bearish OB at {b.get('low', 0):.2f}–{b.get('high', 0):.2f}: resistance zone",
            })

    return order_blocks


def get_ict_analysis(bars: list) -> dict:
    """Full ICT analysis on a set of bars."""
    fvgs = detect_fvg(bars)
    obs = detect_order_block(bars)
    session = get_session_context()

    # Most recent unfilled FVGs are the most actionable
    recent_fvgs = fvgs[-5:] if fvgs else []
    recent_obs = obs[-5:] if obs else []

    return {
        "session": session,
        "fair_value_gaps": recent_fvgs,
        "order_blocks": recent_obs,
        "total_fvgs": len(fvgs),
        "total_obs": len(obs),
        "bullish_fvgs": [f for f in fvgs if f["type"] == "bullish_fvg"],
        "bearish_fvgs": [f for f in fvgs if f["type"] == "bearish_fvg"],
        "bullish_obs": [o for o in obs if o["type"] == "bullish_ob"],
        "bearish_obs": [o for o in obs if o["type"] == "bearish_ob"],
    }
