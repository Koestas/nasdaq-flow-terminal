"""ICT / Smart Money analysis routes."""
from fastapi import APIRouter, Query
from engines.ict import (get_ict_analysis, get_session_context,
                          detect_fvg, extract_session_levels,
                          calc_discount_premium, identify_draw_on_liquidity,
                          detect_equal_highs_lows)
from engines.ict_signals import get_advanced_signals, calc_auto_trade_setup
from engines.risk import calc_account_status
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
    # Try 1-day first; futures (NQ=F, GC=F) often return nothing on weekends → fall back to 5d
    bars = yahoo.get_intraday(symbol, interval="5m")
    if not bars:
        bars = yahoo.get_chart_bars(symbol, "5m", "5d")
    return bars


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


@router.get("/trade-setup")
async def trade_setup(
    symbol: str = Query("QQQ"),
    instrument: str = Query("MNQ", description="MNQ, MES, or MGC"),
    balance: float = Query(25000.0, description="Current account balance"),
    prev_close: float = Query(None, description="Yesterday's EOD closing balance"),
):
    """Auto-calculate a complete trade setup: entry, stop, target, contracts in instrument-native units."""
    bars = await _get_bars(symbol)
    if not bars:
        return {"error": "No bar data available"}

    session_levels = extract_session_levels(bars)
    equal_hl = detect_equal_highs_lows(bars)
    price = session_levels.get("current_price")

    fvgs = detect_fvg(bars)
    dol = identify_draw_on_liquidity(session_levels, equal_hl, price)

    basic = get_ict_analysis(bars, current_price=price)
    long_score = basic.get("long_setup", {}).get("score", 0)
    short_score = basic.get("short_setup", {}).get("score", 0)
    bias = "bullish" if long_score > short_score else "bearish" if short_score > long_score else "neutral"

    secondary = "SPY" if symbol == "QQQ" else "QQQ"
    bars_secondary = await _get_bars(secondary)
    advanced = get_advanced_signals(
        bars=bars, session_levels=session_levels,
        equal_hl=equal_hl, bars_secondary=bars_secondary, bias_direction=bias,
    )

    account_status = calc_account_status(balance, prev_close)

    setup = calc_auto_trade_setup(
        bars=bars,
        fvgs=fvgs,
        advanced_signals=advanced,
        dol=dol,
        instrument=instrument,
        account_status=account_status,
        bias_direction=bias,
    )

    return {
        "symbol": symbol,
        "instrument": instrument.upper(),
        "bias_direction": bias,
        "current_price": price,
        "draw_on_liquidity": dol,
        "setup": setup,
    }
