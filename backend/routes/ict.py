"""ICT / Smart Money analysis routes."""
from fastapi import APIRouter, Query
from engines.ict import (get_ict_analysis, get_session_context,
                          detect_fvg, extract_session_levels,
                          calc_discount_premium, identify_draw_on_liquidity,
                          detect_equal_highs_lows)
from engines.ict_signals import get_advanced_signals
from providers import yahoo, schwab as schwab_provider

router = APIRouter(prefix="/api/ict", tags=["ict"])


async def _get_bars(symbol: str = "QQQ") -> list:
    if schwab_provider.has_tokens():
        try:
            data = await schwab_provider.get_price_history(
                symbol, period_type="day", period=2,
                frequency_type="minute", frequency=5, extended_hours=True,
            )
            if data and data.get("candles"):
                import datetime
                bars = []
                for c in data["candles"]:
                    dt = datetime.datetime.fromtimestamp(c["datetime"] / 1000, tz=datetime.timezone.utc)
                    bars.append({"time": dt.isoformat(), "open": c.get("open"),
                                 "high": c.get("high"), "low": c.get("low"),
                                 "close": c.get("close"), "volume": c.get("volume")})
                return bars
        except Exception:
            pass
    return yahoo.get_intraday(symbol, interval="5m")


@router.get("/analysis")
async def ict_analysis(symbol: str = Query("QQQ")):
    bars = await _get_bars(symbol)
    vwap = yahoo.get_vwap(symbol)
    price = bars[-1]["close"] if bars and bars[-1].get("close") else None
    return get_ict_analysis(bars, vwap=vwap, current_price=price)


@router.get("/session")
async def session_context():
    return get_session_context()


@router.get("/fvgs")
async def fvgs(symbol: str = Query("QQQ")):
    bars = await _get_bars(symbol)
    return {"symbol": symbol, "fvgs": detect_fvg(bars), "bar_count": len(bars)}


@router.get("/levels")
async def session_levels(symbol: str = Query("QQQ")):
    bars = await _get_bars(symbol)
    levels = extract_session_levels(bars)
    price = levels.get("current_price")
    equal_hl = detect_equal_highs_lows(bars)
    return {
        "symbol": symbol, "levels": levels,
        "discount_premium": calc_discount_premium(levels, price),
        "draw_on_liquidity": identify_draw_on_liquidity(levels, equal_hl, price),
        "equal_highs_lows": equal_hl,
    }


@router.get("/advanced")
async def advanced_analysis(symbol: str = Query("QQQ"), secondary: str = Query("SPY")):
    """Advanced ICT signals: MSS/CHoCH, sweeps, OTE, IPDA, SMT, PO3."""
    bars = await _get_bars(symbol)
    bars_secondary = await _get_bars(secondary)

    session_levels = extract_session_levels(bars)
    equal_hl = detect_equal_highs_lows(bars)
    price = session_levels.get("current_price")

    # Get bias from basic analysis to orient OTE direction
    basic = get_ict_analysis(bars, current_price=price)
    long_score = basic.get("long_setup", {}).get("score", 0)
    short_score = basic.get("short_setup", {}).get("score", 0)
    bias = "bullish" if long_score > short_score else "bearish" if short_score > long_score else "neutral"

    advanced = get_advanced_signals(
        bars=bars,
        session_levels=session_levels,
        equal_hl=equal_hl,
        bars_secondary=bars_secondary,
        bias_direction=bias,
    )

    return {
        "symbol": symbol,
        "secondary": secondary,
        "bias_direction": bias,
        "current_price": price,
        **advanced,
    }
