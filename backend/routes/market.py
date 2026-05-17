from fastapi import APIRouter, Query
from providers.yahoo import get_qqq_price, get_vwap, get_leadership_quotes, get_news, get_intraday, get_futures_quotes, get_chart_bars
from engines.bias import BiasEngine
from engines.stats import calc_wave, calc_gex, calc_top_flow, calc_unusual
from engines.ict import get_session_context, extract_session_levels
from providers.yahoo import get_options_chain

router = APIRouter(prefix="/api/market", tags=["market"])
bias_engine = BiasEngine()

_cache: dict = {}


def _fresh_options():
    chain = get_options_chain("QQQ")
    return chain.get("calls", []), chain.get("puts", [])


@router.get("/overview")
async def market_overview():
    try:
        price_data = get_qqq_price()
        vwap = get_vwap("QQQ")
        leadership = get_leadership_quotes()
        calls, puts = _fresh_options()
        wave = calc_wave(calls, puts)
        price = price_data.get("price") or 450.0
        gex_data = calc_gex(calls, puts, price)
        session = get_session_context()

        market_data = {
            "qqq_price": price,
            "qqq_change_pct": price_data.get("change_pct"),
            "vwap": vwap,
            "wave": wave,
            "leadership": leadership,
            "call_wall": gex_data.get("call_wall"),
            "put_wall": gex_data.get("put_wall"),
        }
        bias = bias_engine.calculate(market_data)
        green_count = sum(1 for s in leadership if s.get("bullish"))

        return {
            "price": price_data,
            "vwap": vwap,
            "vwap_status": "above" if (price and vwap and price > vwap) else "below",
            "bias": bias,
            "wave_summary": wave,
            "leadership_summary": {
                "green": green_count,
                "total": len(leadership),
                "breadth_pct": round(green_count / len(leadership) * 100) if leadership else 0,
            },
            "call_wall": gex_data.get("call_wall"),
            "put_wall": gex_data.get("put_wall"),
            "session": session,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/bias")
async def market_bias():
    try:
        price_data = get_qqq_price()
        vwap = get_vwap("QQQ")
        leadership = get_leadership_quotes()
        calls, puts = _fresh_options()
        wave = calc_wave(calls, puts)
        price = price_data.get("price") or 450.0
        gex_data = calc_gex(calls, puts, price)

        market_data = {
            "qqq_price": price,
            "qqq_change_pct": price_data.get("change_pct"),
            "vwap": vwap,
            "wave": wave,
            "leadership": leadership,
            "call_wall": gex_data.get("call_wall"),
            "put_wall": gex_data.get("put_wall"),
        }
        return bias_engine.calculate(market_data)
    except Exception as e:
        return {"error": str(e)}


@router.get("/structure")
async def market_structure():
    try:
        price_data = get_qqq_price()
        vwap = get_vwap("QQQ")
        bars = get_intraday("QQQ", "5m")
        price = price_data.get("price")
        day_high = price_data.get("day_high")
        day_low = price_data.get("day_low")

        # Opening range = first 15 minutes (3 x 5m bars)
        or_high = max((b["high"] for b in bars[:3] if b.get("high")), default=None)
        or_low = min((b["low"] for b in bars[:3] if b.get("low")), default=None)

        return {
            "price": price,
            "vwap": vwap,
            "vwap_status": "above" if (price and vwap and price > vwap) else "below",
            "opening_range_high": or_high,
            "opening_range_low": or_low,
            "day_high": day_high,
            "day_low": day_low,
            "or_position": _or_position(price, or_high, or_low),
            "bars": bars,
        }
    except Exception as e:
        return {"error": str(e)}


def _or_position(price, or_high, or_low):
    if not all([price, or_high, or_low]):
        return "unknown"
    if price > or_high:
        return "above_or"
    if price < or_low:
        return "below_or"
    return "inside_or"


@router.get("/leadership")
async def market_leadership():
    try:
        return {"stocks": get_leadership_quotes()}
    except Exception as e:
        return {"error": str(e)}


@router.get("/news")
async def market_news():
    try:
        return {"news": get_news("QQQ")}
    except Exception as e:
        return {"error": str(e)}


@router.get("/futures")
async def market_futures():
    try:
        return get_futures_quotes()
    except Exception as e:
        return {"error": str(e)}


INTRADAY_INTERVALS = {"1m", "5m", "15m", "30m", "1h"}


@router.get("/chart")
async def market_chart(
    symbol: str = Query(default="NQ=F"),
    interval: str = Query(default="5m"),
    period: str = Query(default="1d"),
):
    try:
        bars = get_chart_bars(symbol, interval, period)

        # For 1-day periods the dataset only contains today's bars, so
        # extract_session_levels can't find yesterday's bars to compute PDH/PDL.
        # Fetch a wider 5-day window at 15m resolution (fast) just for the level calc.
        if period == "1d" and interval in INTRADAY_INTERVALS:
            session_bars = get_chart_bars(symbol, "15m", "5d")
            session_levels = extract_session_levels(session_bars)
        else:
            session_levels = extract_session_levels(bars)

        vwap_data = []
        if interval in INTRADAY_INTERVALS and bars:
            # Group bars by date, compute cumulative VWAP per day resetting at each new day
            from datetime import timezone as _tz
            import pytz
            NY_TZ = pytz.timezone("America/New_York")

            cum_tp_vol = 0.0
            cum_vol = 0.0
            current_day = None

            for b in bars:
                t_raw = b.get("time", "")
                try:
                    if t_raw.endswith("Z"):
                        t_raw = t_raw[:-1] + "+00:00"
                    from datetime import datetime as _dt
                    dt_utc = _dt.fromisoformat(t_raw)
                    dt_et = dt_utc.astimezone(NY_TZ)
                except Exception:
                    continue

                bar_date = dt_et.date()

                # Reset VWAP at each new trading day
                if bar_date != current_day:
                    current_day = bar_date
                    cum_tp_vol = 0.0
                    cum_vol = 0.0

                o, h, l, c, v = b.get("open"), b.get("high"), b.get("low"), b.get("close"), b.get("volume", 0)
                if None in (h, l, c) or v is None:
                    continue

                typical_price = (h + l + c) / 3
                cum_tp_vol += typical_price * v
                cum_vol += v

                if cum_vol > 0:
                    vwap_val = cum_tp_vol / cum_vol
                    vwap_data.append({"time": b["time"], "value": round(vwap_val, 4)})

        return {
            "symbol": symbol,
            "interval": interval,
            "period": period,
            "bars": bars,
            "bar_count": len(bars),
            "session_levels": session_levels,
            "vwap_data": vwap_data,
        }
    except Exception as e:
        return {"error": str(e)}
