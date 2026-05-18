"""ICT / Smart Money analysis routes."""
from fastapi import APIRouter, Query
from engines.ict import (get_ict_analysis, get_session_context,
                          detect_fvg, extract_session_levels,
                          calc_discount_premium, identify_draw_on_liquidity,
                          detect_equal_highs_lows, get_htf_bias, get_day_quality)
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
    daily_bars = yahoo.get_daily_bars(symbol)
    htf = get_htf_bias(daily_bars)
    day_q = get_day_quality()
    result = get_ict_analysis(bars, vwap=vwap, current_price=price)
    result["htf_bias"] = htf
    result["day_quality"] = day_q
    return result


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


@router.get("/htf-bias")
async def htf_bias_endpoint(symbol: str = Query("QQQ")):
    """Higher timeframe daily bias — trend direction, EMAs, structure."""
    daily_bars = yahoo.get_daily_bars(symbol)
    bias = get_htf_bias(daily_bars)
    day_q = get_day_quality()
    return {
        "symbol": symbol,
        "htf_bias": bias,
        "day_quality": day_q,
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


@router.get("/confluence")
async def ict_confluence(symbol: str = Query("NQ=F")):
    """
    Multi-timeframe ICT confluence matrix.
    Returns ICT analysis for 1H → 15m → 5m so traders can
    confirm top-down bias alignment in one API call.
    """
    from providers.yahoo import get_chart_bars

    TF_CONFIG = [
        {"interval": "1h",  "period": "1mo", "label": "1H  (Bias)"},
        {"interval": "15m", "period": "5d",  "label": "15m (Zones)"},
        {"interval": "5m",  "period": "5d",  "label": "5m  (Entry)"},
    ]

    result = {}
    for tf in TF_CONFIG:
        iv, pd, lbl = tf["interval"], tf["period"], tf["label"]
        bars = get_chart_bars(symbol, iv, pd)
        if not bars and pd == "5d":
            bars = get_chart_bars(symbol, iv, "1mo")
        if not bars:
            result[iv] = {"label": lbl, "error": "no data"}
            continue

        sl    = extract_session_levels(bars)
        ehl   = detect_equal_highs_lows(bars)
        price = sl.get("current_price")
        ana   = get_ict_analysis(bars, current_price=price)
        long_sc  = ana.get("long_setup",  {}).get("score", 0)
        short_sc = ana.get("short_setup", {}).get("score", 0)
        bias  = ("bullish" if long_sc > short_sc
                 else "bearish" if short_sc > long_sc else "neutral")

        adv = get_advanced_signals(
            bars=bars, session_levels=sl, equal_hl=ehl,
            bars_secondary=[], bias_direction=bias,
        )

        ifvgs   = ana.get("ifvgs") or []
        sweeps  = adv.get("liquidity_sweeps") or []
        struct  = (adv.get("mss_choch") or {}).get("last_structure", "unknown")
        po3     = (adv.get("po3_phase") or {}).get("phase_label", "")
        dol     = ana.get("draw_on_liquidity") or {}
        dp      = ana.get("discount_premium") or {}
        in_ote  = adv.get("in_ote", False)

        result[iv] = {
            "label":       lbl,
            "bias":        bias,
            "long_score":  long_sc,
            "short_score": short_sc,
            "grade":       ana.get("long_setup" if bias == "bullish" else "short_setup", {}).get("grade", "--"),
            "structure":   struct,
            "po3_phase":   po3,
            "zone":        dp.get("zone", ""),
            "zone_pct":    dp.get("position_pct"),
            "dol_direction": dol.get("direction", "neutral"),
            "dol_target":  dol.get("target"),
            "dol_reason":  dol.get("reason", ""),
            "ifvg_count":  len(ifvgs),
            "sweep_count": len(sweeps),
            "recent_sweep": sweeps[-1] if sweeps else None,
            "top_ifvg":    ifvgs[-1] if ifvgs else None,
            "in_ote":      in_ote,
            "current_price": price,
            "session_levels": {
                k: v for k, v in sl.items()
                if v and k in ("asia_high", "asia_low", "london_high", "london_low",
                               "prev_day_high", "prev_day_low", "today_high", "today_low")
            },
        }

    # Overall alignment verdict
    biases = [result[tf["interval"]]["bias"] for tf in TF_CONFIG
              if "error" not in result.get(tf["interval"], {})]
    bull_count = biases.count("bullish")
    bear_count = biases.count("bearish")
    if bull_count == 3:
        alignment = "STRONG BULLISH — all timeframes aligned long"
        align_dir = "bullish"
    elif bear_count == 3:
        alignment = "STRONG BEARISH — all timeframes aligned short"
        align_dir = "bearish"
    elif bull_count == 2:
        alignment = "BULLISH lean — 2/3 timeframes agree, check 5m for entry"
        align_dir = "bullish"
    elif bear_count == 2:
        alignment = "BEARISH lean — 2/3 timeframes agree, check 5m for entry"
        align_dir = "bearish"
    else:
        alignment = "CONFLICTED — timeframes disagree, no trade"
        align_dir = "neutral"

    return {
        "symbol":    symbol,
        "alignment": alignment,
        "align_dir": align_dir,
        "timeframes": result,
    }
