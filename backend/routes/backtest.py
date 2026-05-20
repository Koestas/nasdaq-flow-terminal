"""
Signal backtest engine — replay the ICT strategy over historical data.

For each trading day in the lookback window:
  1. Identify the NY killzone bars (9:30–11:30 AM ET)
  2. Walk bar-by-bar; when a sweep + iFVG setup reaches grade A/A+, record it
  3. Walk forward from entry to see if target or stop is hit first
  4. Aggregate statistics over all simulated trades
"""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta, date
import pytz
import yfinance as yf

from engines.ict import (get_ict_analysis, extract_session_levels,
                         detect_equal_highs_lows, detect_fvg, get_htf_bias)
from engines.ict_signals import get_advanced_signals, _INSTRUMENT_CONFIG

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

NY_TZ   = pytz.timezone("America/New_York")
UTC     = pytz.UTC
KZ_START = (9, 30)   # NY time
KZ_END   = (11, 30)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _parse_bars(df, symbol: str) -> list:
    """Convert a yfinance DataFrame to bar dicts."""
    if df.empty:
        return []
    df = df.reset_index()
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if c[1] in ("", symbol) else c[0] for c in df.columns]
    ts_col = "Datetime" if "Datetime" in df.columns else "Date"
    bars = []
    for _, row in df.iterrows():
        ts = row[ts_col]
        try:
            o = float(row["Open"]); h = float(row["High"])
            l = float(row["Low"]);  c = float(row["Close"])
            v = float(row.get("Volume") or 0)
        except Exception:
            continue
        if None in (o, h, l, c) or any(x != x for x in (o, h, l, c)):
            continue
        bars.append({
            "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "open": round(o, 4), "high": round(h, 4),
            "low":  round(l, 4), "close": round(c, 4), "volume": v or 0,
        })
    return bars


def _download(symbol: str, start: datetime, end: datetime, interval: str) -> list:
    """
    Download bars. For 5m data yfinance caps at ~60 days per request; for longer
    lookbacks we split into 50-day chunks so up to 180 days of 5m data is available.
    """
    if interval != "5m":
        try:
            df = yf.download(symbol, start=start, end=end, interval=interval,
                             progress=False, auto_adjust=True)
            return _parse_bars(df, symbol)
        except Exception:
            return []

    # 5m: fetch in 50-day chunks (yfinance hard-limit is ~60 days)
    all_bars: list = []
    chunk_end = end
    while chunk_end > start:
        chunk_start = max(start, chunk_end - timedelta(days=50))
        try:
            df = yf.download(symbol, start=chunk_start, end=chunk_end,
                             interval="5m", progress=False, auto_adjust=True)
            chunk_bars = _parse_bars(df, symbol)
            all_bars = chunk_bars + all_bars
        except Exception:
            pass
        chunk_end = chunk_start
    # Deduplicate by time
    seen = set()
    unique = []
    for b in all_bars:
        if b["time"] not in seen:
            seen.add(b["time"])
            unique.append(b)
    return sorted(unique, key=lambda b: b["time"])


def _bar_dt(b: dict) -> datetime:
    ts = b["time"].replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(NY_TZ)


def _group_by_day(bars: list) -> dict:
    """Returns {date: [bars]} sorted by time."""
    days: dict = {}
    for b in bars:
        dt = _bar_dt(b)
        d  = dt.date()
        days.setdefault(d, []).append(b)
    return {d: sorted(v, key=lambda x: _bar_dt(x)) for d, v in sorted(days.items())}


# ── Trade simulator ───────────────────────────────────────────────────────────

def _calc_atr(bars: list, period: int = 14) -> float:
    """Average True Range over last `period` bars."""
    if len(bars) < 2:
        return 15.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 15.0
    recent = trs[-period:]
    return sum(recent) / len(recent)


def _calc_sma(bars: list, period: int) -> float | None:
    """Simple moving average of closes over last `period` bars."""
    closes = [b["close"] for b in bars if b.get("close") is not None]
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _calc_rsi(bars: list, period: int = 14) -> float:
    """Wilder RSI. Returns 50.0 if insufficient data."""
    closes = [b["close"] for b in bars if b.get("close") is not None]
    if len(closes) < period + 1:
        return 50.0
    closes = closes[-(period * 3):]  # enough history for smoothing
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


def _calc_adx(bars: list, period: int = 14) -> float:
    """Average Directional Index. Returns 0 if insufficient data."""
    if len(bars) < period + 2:
        return 0.0
    bars = bars[-(period * 3):]
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(bars)):
        h, l, ph, pl, pc = bars[i]["high"], bars[i]["low"], bars[i-1]["high"], bars[i-1]["low"], bars[i-1]["close"]
        up, dn = h - ph, pl - l
        plus_dm.append(up if up > dn and up > 0 else 0)
        minus_dm.append(dn if dn > up and dn > 0 else 0)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    def smooth(arr):
        s = sum(arr[:period])
        result = [s]
        for v in arr[period:]:
            s = s - s / period + v
            result.append(s)
        return result
    str_ = smooth(trs); spdm = smooth(plus_dm); smdm = smooth(minus_dm)
    dx_vals = []
    for i in range(len(str_)):
        if str_[i] == 0:
            continue
        pdi = 100 * spdm[i] / str_[i]
        mdi = 100 * smdm[i] / str_[i]
        dx_vals.append(100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0)
    if not dx_vals:
        return 0.0
    return sum(dx_vals[-period:]) / min(len(dx_vals), period)


def _calc_vwap_at(day_bars: list, before_dt, session_start_mins: int = 0) -> float | None:
    """
    Cumulative VWAP for the day up to (not including) before_dt.
    session_start_mins: if >0, only include bars at or after that minute-of-day
    (e.g. 570 = 9:30 AM ET). Use for 1h data to exclude overnight distortion.
    """
    cum_tpv = cum_vol = 0.0
    for b in day_bars:
        bdt = _bar_dt(b)
        if bdt >= before_dt:
            break
        if session_start_mins > 0:
            bar_mins = bdt.hour * 60 + bdt.minute
            if bar_mins < session_start_mins:
                continue
        h, l, c, v = b["high"], b["low"], b["close"], b.get("volume", 0) or 0
        if None in (h, l, c):
            continue
        cum_tpv += (h + l + c) / 3 * v
        cum_vol += v
    return cum_tpv / cum_vol if cum_vol > 0 else None


def _check_or30_breakout(day_bars: list, bias: str, before_dt) -> bool:
    """
    Returns True if price already broke the first-30-min OR in `bias` direction
    with above-average volume (Coach Dakota / Coach Jay urgency trade requirement).
    """
    or_bars = [b for b in day_bars
               if 570 <= _bar_dt(b).hour * 60 + _bar_dt(b).minute < 600]
    if len(or_bars) < 3:
        return False
    or_h = max(b["high"] for b in or_bars)
    or_l = min(b["low"] for b in or_bars)
    avg_vol = sum(b.get("volume", 0) for b in or_bars) / len(or_bars) or 1
    post = [b for b in day_bars
            if _bar_dt(b).hour * 60 + _bar_dt(b).minute >= 600
            and _bar_dt(b) < before_dt]
    for b in post:
        vol = b.get("volume", 0) or 0
        if bias == "bullish" and b["high"] > or_h and vol > avg_vol * 0.85:
            return True
        if bias == "bearish" and b["low"] < or_l and vol > avg_vol * 0.85:
            return True
    return False


def _find_or30_setup(day_bars: list, all_prior_bars: list,
                     instrument: str = "MNQ",
                     htf_direction: str = "neutral",
                     prior_days: dict | None = None,
                     vol_regime_pct: float = 4.0) -> dict | None:
    """
    Coach Dakota / Coach Jay urgency trade: OR30 breakout with above-average volume.
    Runs as a secondary track on days the ICT killzone setup doesn't fire.

    Entry: close of the first bar that breaks the OR with vol > 1.2x OR average.
    Stop: below OR low (longs) / above OR high (shorts) + instrument buffer.
    Target: 1.5R fixed.
    """
    # Apply same day-level vol regime filter as ICT model
    if prior_days:
        threshold = vol_regime_pct / 100.0
        prior_list = list(prior_days.values())
        for prev_bars in prior_list[-3:]:
            if prev_bars and prev_bars[0]["open"] > 0:
                day_range_pct = (max(b["high"] for b in prev_bars) -
                                 min(b["low"] for b in prev_bars)) / prev_bars[0]["open"]
                if day_range_pct > threshold:
                    return None  # post-crash regime — skip

    # Build OR (9:30–10:00 bars = minutes 570–599)
    or_bars = [b for b in day_bars
               if 570 <= _bar_dt(b).hour * 60 + _bar_dt(b).minute < 600]
    if len(or_bars) < 3:
        return None
    or_h   = max(b["high"]    for b in or_bars)
    or_l   = min(b["low"]     for b in or_bars)
    or_rng = or_h - or_l
    if or_rng < 5:  # degenerate OR (gap or holiday) — skip
        return None
    avg_vol = sum(b.get("volume", 0) for b in or_bars) / len(or_bars) or 1

    config  = _INSTRUMENT_CONFIG.get(instrument.upper(), _INSTRUMENT_CONFIG["MNQ"])
    buf     = config["stop_buffer"]
    min_st  = config["min_stop_pts"]

    # Scan post-OR bars (10:00–11:30) for first clean breakout with volume
    post_bars = [b for b in day_bars
                 if 600 <= _bar_dt(b).hour * 60 + _bar_dt(b).minute <= 690]  # 10:00–11:30
    for idx, b in enumerate(post_bars):
        vol = b.get("volume", 0) or 0
        if vol < avg_vol * 1.2:
            continue  # volume confirmation required

        if b["high"] > or_h:
            bias = "bullish"
            if htf_direction in ("bearish", "strong_bearish", "bearish_lean"):
                continue
            entry     = b["close"]
            stop      = max(or_l - buf, entry - 2 * or_rng)
            stop_dist = entry - stop
            if stop_dist < min_st:
                continue
            target    = entry + 1.5 * stop_dist
            remaining = post_bars[idx + 1:] + [
                bb for bb in day_bars
                if _bar_dt(bb).hour * 60 + _bar_dt(bb).minute > 690
            ]
            return {
                "bar_index": idx,
                "entry_bar": b,
                "remaining_bars": remaining,
                "direction": bias,
                "entry": round(entry, 2),
                "stop":  round(stop, 2),
                "target": round(target, 2),
                "stop_dist": round(stop_dist, 2),
                "reward_dist": round(abs(target - entry), 2),
                "rr_ratio": 1.5,
                "grade": "B+",
                "score": 55,
                "sweep_label": "OR30-breakout",
                "fvg_zone": f"{or_l:.2f}–{or_h:.2f}",
                "dol_reason": "OR30 urgency trade",
            }

        if b["low"] < or_l:
            bias = "bearish"
            if htf_direction in ("bullish", "strong_bullish", "bullish_lean"):
                continue
            entry     = b["close"]
            stop      = min(or_h + buf, entry + 2 * or_rng)
            stop_dist = stop - entry
            if stop_dist < min_st:
                continue
            target    = entry - 1.5 * stop_dist
            remaining = post_bars[idx + 1:] + [
                bb for bb in day_bars
                if _bar_dt(bb).hour * 60 + _bar_dt(bb).minute > 690
            ]
            return {
                "bar_index": idx,
                "entry_bar": b,
                "remaining_bars": remaining,
                "direction": bias,
                "entry": round(entry, 2),
                "stop":  round(stop, 2),
                "target": round(target, 2),
                "stop_dist": round(stop_dist, 2),
                "reward_dist": round(abs(target - entry), 2),
                "rr_ratio": 1.5,
                "grade": "B+",
                "score": 55,
                "sweep_label": "OR30-breakout",
                "fvg_zone": f"{or_l:.2f}–{or_h:.2f}",
                "dol_reason": "OR30 urgency trade",
            }

    return None


def _day_range_ratio(day_bars: list, prior_days: dict) -> float:
    """
    Today's OR range vs 5-day average range.
    High ratio = chaotic/gap day — risky for setups.
    """
    if not day_bars or not prior_days:
        return 1.0
    recent = list(prior_days.values())[-5:]
    if not recent:
        return 1.0
    avg_range = sum(
        max(b["high"] for b in d) - min(b["low"] for b in d)
        for d in recent if d
    ) / len(recent)
    if avg_range == 0:
        return 1.0
    today_range = max(b["high"] for b in day_bars) - min(b["low"] for b in day_bars)
    return today_range / avg_range


def _simulate_trade(entry_price: float, stop: float, target: float,
                    direction: str, forward_bars: list,
                    stop_dist: float = 0.0) -> dict:
    """
    Walk forward bars. Uses a partial-TP strategy (prop-trader approach):
    - At +1R (entry + stop_dist): take 50% off, move stop to breakeven
    - At +2R (target): full exit — win
    - If stopped at breakeven after 1R hit: partial_win
    - If stopped before 1R: loss
    - EOD close: win/loss based on direction vs entry (breakeven counts as partial_win)
    """
    partial_r    = entry_price + stop_dist if direction == "bullish" else entry_price - stop_dist
    be_stop      = entry_price  # breakeven stop after partial
    partial_hit  = False

    for b in forward_bars:
        h, l = b.get("high", 0), b.get("low", 0)
        if direction == "bullish":
            if not partial_hit:
                if l <= stop:
                    return {"result": "loss", "exit_price": stop}
                if h >= partial_r:
                    partial_hit = True  # 1R hit — move stop to BE, continue for 2R
            else:
                if l <= be_stop:
                    return {"result": "partial_win", "exit_price": be_stop}
                if h >= target:
                    return {"result": "win", "exit_price": target}
        else:
            if not partial_hit:
                if h >= stop:
                    return {"result": "loss", "exit_price": stop}
                if l <= partial_r:
                    partial_hit = True
            else:
                if h >= be_stop:
                    return {"result": "partial_win", "exit_price": be_stop}
                if l <= target:
                    return {"result": "win", "exit_price": target}

    last = forward_bars[-1]["close"] if forward_bars else entry_price
    if partial_hit:
        return {"result": "partial_win", "exit_price": last, "eod": True}
    if direction == "bullish":
        eod_result = "win" if last > entry_price else "loss"
    else:
        eod_result = "win" if last < entry_price else "loss"
    return {"result": eod_result, "exit_price": last, "eod": True}


# ── 30-min VWAP bias (Coach Dakota filter) ───────────────────────────────────

def _get_30min_vwap_bias(day_bars: list, bar_dt) -> str:
    """
    At bar_dt, check whether the most recently CLOSED 30-minute candle's close
    is above or below the day's cumulative VWAP up to that point.
    Returns 'bullish', 'bearish', or 'neutral' (neutral = no completed 30-min yet).
    """
    bar_mins = bar_dt.hour * 60 + bar_dt.minute

    # Day VWAP up to (not including) current bar
    cum_tpv = cum_vol = 0.0
    for b in day_bars:
        bdt = _bar_dt(b)
        if bdt >= bar_dt:
            break
        h, l, c, v = b["high"], b["low"], b["close"], b.get("volume") or 0
        cum_tpv += (h + l + c) / 3 * v
        cum_vol += v

    if cum_vol == 0:
        return "neutral"
    vwap = cum_tpv / cum_vol

    # Most recently completed 30-min window boundaries
    current_period_start = (bar_mins // 30) * 30
    last_period_start    = current_period_start - 30
    last_period_end      = current_period_start

    period_bars = [
        b for b in day_bars
        if last_period_start
           <= _bar_dt(b).hour * 60 + _bar_dt(b).minute
           <  last_period_end
    ]
    if not period_bars:
        return "neutral"   # no completed 30-min candle yet (first 30 min of session)

    period_close = period_bars[-1]["close"]
    if period_close > vwap:   return "bullish"
    if period_close < vwap:   return "bearish"
    return "neutral"


# ── Per-day signal detection ──────────────────────────────────────────────────

def _find_killzone_setup(day_bars: list, all_prior_bars: list, instrument: str = "MNQ",
                         start_bar_index: int = 6, htf_direction: str = "neutral",
                         used_entries: list | None = None,
                         kz_start: tuple = (9, 30), kz_end: tuple = (11, 30),
                         prior_days: dict | None = None,
                         min_score: int = 65,
                         sweep_max_age_mins: int = 90,
                         require_mss: bool = True,
                         vol_regime_pct: float = 4.0,
                         min_kz_bars: int = 6,
                         session_vwap_start: int = 0,
                         fvg_prox_mult: float = 3.0,
                         atr_min_mult: float = 2.0) -> dict | None:
    """
    Walk through a killzone bar-by-bar; return the first A/A+ setup with sweep + iFVG.
    htf_direction: daily bias — filters out contra-trend setups.
    used_entries: entries already taken today — prevents re-entering same FVG zone.
    min_score: ICT score floor (65 AM standard; 68 PM; 70 Monday).
    sweep_max_age_mins: freshness window relative to bar_dt (90 AM; 330 PM covers full session).
    require_mss: True for AM (strict); False for PM (structure already established in AM session).
    """
    kz_bars = [
        b for b in day_bars
        if kz_start[0] * 60 + kz_start[1]
           <= _bar_dt(b).hour * 60 + _bar_dt(b).minute
           <= kz_end[0] * 60 + kz_end[1]
    ]
    if len(kz_bars) < min_kz_bars:
        return None

    # Build context from prior bars + bars up to this point in killzone
    for i in range(start_bar_index, len(kz_bars) + 1):
        # Use up to 200 prior bars + current killzone window for context
        context = (all_prior_bars + day_bars)[-200:] + kz_bars[:i]

        bar_dt   = _bar_dt(kz_bars[i - 1])
        sl  = extract_session_levels(context, reference_dt=bar_dt)
        ehl = detect_equal_highs_lows(context)
        price = kz_bars[i - 1]["close"]

        analysis = get_ict_analysis(context, current_price=price, reference_dt=bar_dt)
        long_sc  = analysis.get("long_setup",  {}).get("score", 0)
        short_sc = analysis.get("short_setup", {}).get("score", 0)
        bias     = ("bullish" if long_sc > short_sc
                    else "bearish" if short_sc > long_sc else "neutral")
        if bias == "neutral":
            continue

        # HTF filter: only trade in the direction of the daily trend
        if htf_direction in ("bullish", "strong_bullish", "bullish_lean") and bias == "bearish":
            continue
        if htf_direction in ("bearish", "strong_bearish", "bearish_lean") and bias == "bullish":
            continue

        # 30-min VWAP filter (Coach Dakota): last closed 30-min candle must agree with bias
        vwap_bias = _get_30min_vwap_bias(day_bars, bar_dt)
        if vwap_bias != "neutral" and vwap_bias != bias:
            continue

        # ── QUALITY FILTERS ────────────────────────────────────────────────────

        # 1. Minimum ICT score (parameterised — 65 standard, 70 on Monday/PM session)
        setup_score_pre = long_sc if bias == "bullish" else short_sc
        if setup_score_pre < min_score:
            continue

        # 2. VWAP position: price must be on correct side of day VWAP
        #    Tolerance: 0.3% (50pt on NQ) — tight enough to exclude clear contra-trend entries
        vwap_now = _calc_vwap_at(day_bars, bar_dt, session_start_mins=session_vwap_start)
        if vwap_now:
            if bias == "bullish" and price < vwap_now * 0.997:
                continue   # price clearly below VWAP = skip long
            if bias == "bearish" and price > vwap_now * 1.003:
                continue   # price clearly above VWAP = skip short

        # 3. 200 SMA (5-min) trend filter — skip only when price is strongly contra-trend
        #    200 × 5m = 1000 min ≈ 2.5 trading days; context must be large enough
        sma200 = _calc_sma(context, 200)
        if sma200 is not None:
            if bias == "bullish" and price < sma200 * 0.996:
                continue   # >0.4% below 200 SMA = skip long
            if bias == "bearish" and price > sma200 * 1.004:
                continue   # >0.4% above 200 SMA = skip short

        # 4. ADX: skip ranging/choppy markets — ICT setups fail most in no-trend zones
        adx = _calc_adx(context[-60:])
        if adx < 12:
            continue

        # 5. RSI: don't chase overbought longs or oversold shorts
        rsi = _calc_rsi(context[-60:])
        if bias == "bullish" and rsi > 75:
            continue
        if bias == "bearish" and rsi < 25:
            continue

        # 6. Avoid entries when market is in extreme volatility (tariff/FOMC/VIX-spike mode)
        if prior_days:
            rr = _day_range_ratio(day_bars, prior_days)
            if rr > 2.2:
                continue  # today is >2.2× normal range = chaotic/fake setups

            # 3-day volatility regime filter: if ANY of the last 3 trading days had an
            # intraday range > vol_regime_pct, market is in post-event carry-over mode.
            # Default 4% for NQ (680pts on NQ@17k); Gold uses 2.5%; ES uses 3%
            prior_list = list(prior_days.values())
            skip_volatile = False
            threshold = vol_regime_pct / 100.0
            for prev_bars in prior_list[-3:]:
                if prev_bars and prev_bars[0]["open"] > 0:
                    day_range_pct = (max(b["high"] for b in prev_bars) -
                                     min(b["low"] for b in prev_bars)) / prev_bars[0]["open"]
                    if day_range_pct > threshold:
                        skip_volatile = True
                        break
            if skip_volatile:
                continue

        adv = get_advanced_signals(
            bars=context, session_levels=sl, equal_hl=ehl,
            bars_secondary=[], bias_direction=bias,
        )

        sweeps = adv.get("liquidity_sweeps") or []
        # Sweep freshness: within sweep_max_age_mins of current bar_dt
        # AM=90min (tight — only same-session sweeps); PM=330min (full day, AM sweeps still valid)
        recent = []
        for s in sweeps:
            if s.get("direction") != bias:
                continue
            s_time = s.get("time")
            if s_time:
                try:
                    s_dt = _bar_dt({"time": s_time})
                    mins_since = (bar_dt - s_dt).total_seconds() / 60
                    if 0 <= mins_since <= sweep_max_age_mins:
                        recent.append(s)
                except Exception:
                    recent.append(s)
            else:
                recent.append(s)
        if not recent:
            continue

        # MSS/CHoCH confirmation: required for AM; skipped for PM (structure set by AM session)
        if require_mss:
            mss = adv.get("mss_choch") or {}
            last_struct = (mss.get("last_structure") or "").lower()
            if bias == "bullish" and "bullish" not in last_struct:
                continue
            if bias == "bearish" and "bearish" not in last_struct:
                continue

        ifvgs = analysis.get("ifvgs") or []
        aligned = [f for f in ifvgs
                   if f.get("base_type") == f"{'bullish' if bias=='bullish' else 'bearish'}_fvg"]
        if not aligned:
            continue

        setup_score = long_sc if bias == "bullish" else short_sc
        setup_obj   = analysis.get("long_setup" if bias == "bullish" else "short_setup", {})
        grade       = setup_obj.get("grade") or (
            "A+" if setup_score >= 75 else
            "A"  if setup_score >= 55 else
            "B"  if setup_score >= 35 else "C"
        )
        if grade not in ("A+", "A"):
            continue

        # Build entry / stop / target in price units
        fvg     = min(aligned, key=lambda f: abs(f["mid"] - price))
        entry   = fvg["mid"]   # midpoint entry — less vulnerable to edge stop hunts
        config  = _INSTRUMENT_CONFIG.get(instrument, _INSTRUMENT_CONFIG["MNQ"])
        buf     = config["stop_buffer"]
        min_st  = config["min_stop_pts"]

        # Skip stale FVGs — price must be near the zone (within fvg_prox_mult× the gap size)
        if abs(price - fvg["mid"]) > fvg["size"] * fvg_prox_mult + min_st:
            continue

        # Prevent re-entering the same FVG zone already used today
        if used_entries and any(abs(entry - prev) < min_st for prev in used_entries):
            continue

        # ATR-based stop: atr_min_mult × ATR gives room for normal noise
        # Use atr_min_mult=0 for 1h data (ATR is ~135pts/bar, would blow the cap)
        atr      = _calc_atr(context[-50:])
        atr_dist = atr * atr_min_mult

        if bias == "bullish":
            sweep_stop = (min(recent[-1].get("wick_low",  recent[-1]["level"]), fvg["bottom"]) - buf)
            sweep_dist = entry - sweep_stop
            stop_dist  = max(sweep_dist, atr_dist, min_st)
            stop       = entry - stop_dist
        else:
            sweep_stop = (max(recent[-1].get("wick_high", recent[-1]["level"]), fvg["top"]) + buf)
            sweep_dist = sweep_stop - entry
            stop_dist  = max(sweep_dist, atr_dist, min_st)
            stop       = entry + stop_dist

        # ATR stop cap: if stop is too wide, market is too volatile — skip trade
        # Prevents outsized losses on tariff/FOMC/VIX-spike days
        max_stop = {"MNQ": 120.0, "MES": 60.0, "MGC": 12.0}.get(instrument.upper(), 120.0)
        if stop_dist > max_stop:
            continue

        # Target: use DOL if it gives ≥ 1.5R (more realistic than requiring 2R)
        dol       = analysis.get("draw_on_liquidity") or {}
        dol_tgt   = dol.get("target")
        if dol_tgt and abs(dol_tgt - entry) >= 1.5 * stop_dist:
            target = dol_tgt
        else:
            target = (entry + 2.0 * stop_dist if bias == "bullish"
                      else entry - 2.0 * stop_dist)

        return {
            "bar_index": i,
            "entry_bar": kz_bars[i - 1],
            "remaining_bars": kz_bars[i:] + [
                b for b in day_bars
                if _bar_dt(b).hour * 60 + _bar_dt(b).minute > KZ_END[0] * 60 + KZ_END[1]
            ],
            "direction": bias,
            "entry": round(entry, 2),
            "stop":  round(stop, 2),
            "target": round(target, 2),
            "stop_dist": round(stop_dist, 2),
            "reward_dist": round(abs(target - entry), 2),
            "rr_ratio": round(abs(target - entry) / stop_dist, 2) if stop_dist else 0,
            "grade": grade,
            "score": setup_score,
            "sweep_label": recent[-1].get("label", "sweep"),
            "fvg_zone": f"{fvg['bottom']:.2f}–{fvg['top']:.2f}",
            "dol_reason": dol.get("reason", ""),
        }

    return None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/run")
def run_backtest(
    symbol:            str = Query(default="NQ=F", description="NQ=F, ES=F, or GC=F"),
    instrument:        str = Query(default="MNQ"),
    lookback_days:     int = Query(default=30, ge=5, le=90),
    contracts:         int = Query(default=1, ge=1, le=20, description="Number of contracts per trade"),
    daily_loss_limit:  int = Query(default=1000, ge=100, le=5000, description="Daily loss limit in USD"),
    min_score:         int = Query(default=0,  ge=0, le=100, description="Score floor override (0=auto per day)"),
    require_mss:       int = Query(default=1,  ge=0, le=1,   description="1=require MSS confirmation, 0=skip MSS"),
    vol_regime_pct:    float = Query(default=4.0, ge=1.0, le=10.0, description="3-day volatility regime threshold %"),
):
    config     = _INSTRUMENT_CONFIG.get(instrument.upper(), _INSTRUMENT_CONFIG["MNQ"])
    usd_per_pt = config["dollars_per_point"] * contracts

    end_dt   = datetime.now(tz=UTC)
    start_dt = end_dt - timedelta(days=lookback_days + 3)

    bars_all = _download(symbol, start_dt, end_dt + timedelta(hours=2), "5m")
    if not bars_all:
        return {"error": f"No data returned for {symbol}"}

    # Daily bars for HTF bias — go back 90 days so early backtest days have enough data
    daily_bars_all = _download(symbol, end_dt - timedelta(days=90), end_dt, "1d")

    by_day  = _group_by_day(bars_all)
    trades  = []
    running_pnl  = 0.0
    equity_curve = []

    days_sorted = sorted(by_day.keys())
    for i, d in enumerate(days_sorted):
        if d.weekday() >= 5:   # skip weekends
            continue

        day_bars   = by_day[d]
        prior_bars = []
        for pd in days_sorted[:i]:
            prior_bars.extend(by_day[pd])
        prior_bars = prior_bars[-300:]  # keep last 300 bars as context

        # HTF bias: use daily bars up to (but not including) this day
        htf_bars = [b for b in daily_bars_all if b["time"][:10] < d.isoformat()]
        htf_result = get_htf_bias(htf_bars) if len(htf_bars) >= 22 else {"bias": "neutral"}
        htf_dir = htf_result.get("bias", "neutral")

        # Determine day quality tier — affects score minimum for that session
        # Mon: choppier open dynamics → score 70
        # Fri: pre-weekend chop — require 68+ (was 72, too strict — never fired)
        # Tue–Thu: peak ICT session quality → score 65
        # min_score param overrides (0 = use auto tier)
        is_monday = d.weekday() == 0
        is_friday = d.weekday() == 4
        if min_score > 0:
            am_min_score = min_score
        elif is_monday:
            am_min_score = 70
        elif is_friday:
            am_min_score = 68
        else:
            am_min_score = 65
        prior_map = {pd: by_day[pd] for pd in days_sorted[:i]}

        used_entries: list = []
        day_traded   = False
        trades_today = 0
        next_bar_idx = 6  # start first scan at bar 6 of killzone

        # ── AM Killzone (9:30–11:30 ET) — up to 2 trades/day ─────────────────
        # First trade always required. Second trade (reload) only allowed when the
        # first trade resolved as win or partial_win (not loss). This matches how
        # prop traders reload after a confirmed profitable setup clears.
        while trades_today < 2:
            am_setup = _find_killzone_setup(
                day_bars, prior_bars,
                instrument=instrument.upper(),
                start_bar_index=next_bar_idx,
                htf_direction=htf_dir,
                used_entries=used_entries,
                kz_start=(9, 30), kz_end=(11, 30),
                prior_days=prior_map,
                min_score=am_min_score,
                sweep_max_age_mins=90,
                require_mss=bool(require_mss),
                vol_regime_pct=vol_regime_pct,
            )

            if not am_setup:
                break

            outcome = _simulate_trade(
                am_setup["entry"], am_setup["stop"], am_setup["target"],
                am_setup["direction"], am_setup["remaining_bars"],
                stop_dist=am_setup["stop_dist"],
            )
            am_result = outcome["result"]
            sd = am_setup["stop_dist"]

            if am_result == "win":
                pts = (outcome["exit_price"] - am_setup["entry"]) if am_setup["direction"] == "bullish" \
                      else (am_setup["entry"] - outcome["exit_price"])
            elif am_result == "partial_win":
                pts = sd * 0.5
            else:
                pts = (outcome["exit_price"] - am_setup["entry"]) if am_setup["direction"] == "bullish" \
                      else (am_setup["entry"] - outcome["exit_price"])

            pnl = round(pts * usd_per_pt, 2)
            running_pnl += pnl
            day_traded = True
            trades_today += 1
            used_entries.append(am_setup["entry"])
            next_bar_idx = am_setup["bar_index"] + 2  # resume scan 2 bars after last entry

            session_label = "AM" if trades_today == 1 else "AM2"
            trades.append({
                "date": d.isoformat(), "day": d.strftime("%a %b %d"),
                "session": session_label, "direction": am_setup["direction"],
                "grade": am_setup["grade"], "score": am_setup["score"],
                "htf_dir": htf_dir,
                "entry": am_setup["entry"], "stop": am_setup["stop"],
                "target": am_setup["target"], "exit_price": outcome["exit_price"],
                "result": am_result, "eod": outcome.get("eod", False),
                "pts": round(pts, 2), "pnl": pnl,
                "rr_achieved": round(pts / sd, 2) if sd else 0,
                "rr_planned": am_setup["rr_ratio"], "stop_dist": sd,
                "sweep": am_setup["sweep_label"], "fvg_zone": am_setup["fvg_zone"],
                "dol": am_setup["dol_reason"], "running_pnl": round(running_pnl, 2),
            })
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": True})

            # Only reload after a win or partial_win; stop on loss
            if am_result == "loss":
                break

        # OR30 urgency trade — secondary track on days the ICT model didn't fire.
        # Coach Dakota setup: first bar to break the OR range with 1.2x OR average volume.
        # Lower quality than ICT (B+ grade, 55 score) but adds trades on clean trending days.
        if not day_traded and not is_monday and not is_friday:
            or_setup = _find_or30_setup(
                day_bars, prior_bars,
                instrument=instrument.upper(),
                htf_direction=htf_dir,
                prior_days=prior_map,
                vol_regime_pct=vol_regime_pct,
            )
            if or_setup:
                or_outcome = _simulate_trade(
                    or_setup["entry"], or_setup["stop"], or_setup["target"],
                    or_setup["direction"], or_setup["remaining_bars"],
                    stop_dist=or_setup["stop_dist"],
                )
                or_res = or_outcome["result"]
                sd2    = or_setup["stop_dist"]
                if or_res == "win":
                    pts2 = (or_outcome["exit_price"] - or_setup["entry"]) if or_setup["direction"] == "bullish" \
                           else (or_setup["entry"] - or_outcome["exit_price"])
                elif or_res == "partial_win":
                    pts2 = sd2 * 0.5
                else:
                    pts2 = (or_outcome["exit_price"] - or_setup["entry"]) if or_setup["direction"] == "bullish" \
                           else (or_setup["entry"] - or_outcome["exit_price"])
                pnl2 = round(pts2 * usd_per_pt, 2)
                running_pnl += pnl2
                day_traded = True
                trades.append({
                    "date": d.isoformat(), "day": d.strftime("%a %b %d"),
                    "session": "OR30", "direction": or_setup["direction"],
                    "grade": or_setup["grade"], "score": or_setup["score"],
                    "htf_dir": htf_dir,
                    "entry": or_setup["entry"], "stop": or_setup["stop"],
                    "target": or_setup["target"], "exit_price": or_outcome["exit_price"],
                    "result": or_res, "eod": or_outcome.get("eod", False),
                    "pts": round(pts2, 2), "pnl": pnl2,
                    "rr_achieved": round(pts2 / sd2, 2) if sd2 else 0,
                    "rr_planned": or_setup["rr_ratio"], "stop_dist": sd2,
                    "sweep": or_setup["sweep_label"], "fvg_zone": or_setup["fvg_zone"],
                    "dol": or_setup["dol_reason"], "running_pnl": round(running_pnl, 2),
                })
                equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": True})

        if not day_traded:
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": False})

    # ── Statistics ────────────────────────────────────────────────────────────
    wins   = [t for t in trades if t["result"] in ("win", "partial_win")]
    losses = [t for t in trades if t["result"] == "loss"]
    total  = len(trades)
    win_rate   = round(len(wins) / total * 100, 1) if total else 0
    avg_win    = round(sum(t["pnl"] for t in wins)   / len(wins),   2) if wins   else 0
    avg_loss   = round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0
    pf         = round(abs(sum(t["pnl"] for t in wins)) /
                       max(abs(sum(t["pnl"] for t in losses)), 0.01), 2)
    avg_rr     = round(sum(t["rr_achieved"] for t in trades) / total, 2) if total else 0
    best_trade  = max(trades, key=lambda t: t["pnl"], default=None)
    worst_trade = min(trades, key=lambda t: t["pnl"], default=None)
    max_drawdown = _calc_max_drawdown(equity_curve)

    trading_days = len([d for d in days_sorted if d.weekday() < 5])
    monthly_projection = round(running_pnl / max(lookback_days, 1) * 21, 2)  # 21 trading days/month

    return {
        "symbol":        symbol,
        "instrument":    instrument.upper(),
        "contracts":     contracts,
        "lookback_days": lookback_days,
        "trading_days":  trading_days,
        "stats": {
            "total_trades":        total,
            "wins":                len(wins),
            "losses":              len(losses),
            "eod_closes":          len([t for t in trades if t.get("eod")]),
            "win_rate":            win_rate,
            "total_pnl":           round(running_pnl, 2),
            "monthly_projection":  monthly_projection,
            "avg_win":             avg_win,
            "avg_loss":            avg_loss,
            "profit_factor":       pf,
            "avg_rr":              avg_rr,
            "max_drawdown":        max_drawdown,
            "best_trade":          best_trade,
            "worst_trade":         worst_trade,
        },
        "trades":        trades,
        "equity_curve":  equity_curve,
    }


def _calc_max_drawdown(equity_curve: list) -> float:
    peak, max_dd = 0.0, 0.0
    for e in equity_curve:
        pnl = e["pnl"]
        if pnl > peak:
            peak = pnl
        dd = peak - pnl
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


# ── Asia / Overnight Session Backtest ─────────────────────────────────────────

def _run_session_backtest(
    symbol: str, instrument: str, lookback_days: int,
    contracts: int, daily_loss_limit: int,
    kz_start: tuple, kz_end: tuple,
    session_label: str,
    start_bar_index: int = 3,
) -> dict:
    """
    Shared engine for any session (NY, Asia, London).
    kz_start / kz_end are ET hour/minute tuples.
    For overnight sessions, bars span two calendar dates — handled via _bar_dt.
    """
    config     = _INSTRUMENT_CONFIG.get(instrument.upper(), _INSTRUMENT_CONFIG["MNQ"])
    usd_per_pt = config["dollars_per_point"] * contracts

    end_dt   = datetime.now(tz=UTC)
    start_dt = end_dt - timedelta(days=lookback_days + 5)

    bars_all = _download(symbol, start_dt, end_dt + timedelta(hours=2), "5m")
    if not bars_all:
        return {"error": f"No data for {symbol}"}

    daily_bars_all = _download(symbol, end_dt - timedelta(days=90), end_dt, "1d")
    by_day  = _group_by_day(bars_all)
    trades  = []
    running_pnl  = 0.0
    equity_curve = []
    days_sorted  = sorted(by_day.keys())

    for i, d in enumerate(days_sorted):
        if d.weekday() >= 5:
            continue

        day_bars   = by_day[d]
        prior_bars = []
        for pd in days_sorted[:i]:
            prior_bars.extend(by_day[pd])
        prior_bars = prior_bars[-300:]

        # For Asia session, combine yesterday evening + today early-AM bars
        # by_day groups by ET date, so Asia bars (7PM-11PM) live on the *previous* day key
        if kz_start[0] >= 17:  # evening session
            prev_idx = i - 1
            prev_day = days_sorted[prev_idx] if prev_idx >= 0 else None
            session_bars = (by_day.get(prev_day, []) if prev_day else []) + day_bars
        else:
            session_bars = day_bars

        htf_bars = [b for b in daily_bars_all if b["time"][:10] < d.isoformat()]
        htf_result = get_htf_bias(htf_bars) if len(htf_bars) >= 22 else {"bias": "neutral"}
        htf_dir = htf_result.get("bias", "neutral")

        day_losses = 0
        next_start = start_bar_index
        day_traded = False
        used_entries: list = []

        while day_losses < 1:
            day_loss_usd = sum(t["pnl"] for t in trades if t["date"] == d.isoformat())
            if day_loss_usd <= -daily_loss_limit:
                break

            setup = _find_killzone_setup(
                session_bars, prior_bars,
                instrument=instrument.upper(),
                start_bar_index=next_start,
                htf_direction=htf_dir,
                used_entries=used_entries,
                kz_start=kz_start, kz_end=kz_end,
                prior_days={pd: by_day[pd] for pd in days_sorted[:i]},
            )
            if not setup:
                break

            sd = setup["stop_dist"]
            outcome = _simulate_trade(
                setup["entry"], setup["stop"], setup["target"],
                setup["direction"], setup["remaining_bars"],
                stop_dist=sd,
            )
            res = outcome["result"]
            exit_p = outcome["exit_price"]
            if res == "win":
                pts = (exit_p - setup["entry"]) if setup["direction"] == "bullish" \
                      else (setup["entry"] - exit_p)
            elif res == "partial_win":
                pts = sd * 0.5
            else:
                pts = (exit_p - setup["entry"]) if setup["direction"] == "bullish" \
                      else (setup["entry"] - exit_p)

            pnl = round(pts * usd_per_pt, 2)
            running_pnl += pnl
            day_traded = True

            trades.append({
                "date": d.isoformat(), "day": d.strftime("%a %b %d"),
                "session": session_label,
                "direction": setup["direction"], "grade": setup["grade"],
                "score": setup["score"], "htf_dir": htf_dir,
                "entry": setup["entry"], "stop": setup["stop"],
                "target": setup["target"], "exit_price": exit_p,
                "result": res, "eod": outcome.get("eod", False),
                "pts": round(pts, 2), "pnl": pnl,
                "rr_achieved": round(pts / sd, 2) if sd else 0,
                "rr_planned": setup["rr_ratio"],
                "stop_dist": sd,
                "running_pnl": round(running_pnl, 2),
            })
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": True})

            if res == "loss":
                day_losses += 1
            break

        if not day_traded:
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": False})

    wins   = [t for t in trades if t["result"] in ("win", "partial_win")]
    losses = [t for t in trades if t["result"] == "loss"]
    total  = len(trades)
    win_rate = round(len(wins) / total * 100, 1) if total else 0
    avg_win  = round(sum(t["pnl"] for t in wins)   / len(wins),   2) if wins   else 0
    avg_loss = round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0
    pf       = round(abs(sum(t["pnl"] for t in wins)) /
                     max(abs(sum(t["pnl"] for t in losses)), 0.01), 2)
    avg_rr   = round(sum(t["rr_achieved"] for t in trades) / total, 2) if total else 0
    monthly_projection = round(running_pnl / max(lookback_days, 1) * 21, 2)

    return {
        "symbol": symbol, "instrument": instrument.upper(),
        "session": session_label, "contracts": contracts,
        "lookback_days": lookback_days,
        "stats": {
            "total_trades": total, "wins": len(wins), "losses": len(losses),
            "eod_closes": len([t for t in trades if t.get("eod")]),
            "win_rate": win_rate, "total_pnl": round(running_pnl, 2),
            "monthly_projection": monthly_projection,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "profit_factor": pf, "avg_rr": avg_rr,
            "max_drawdown": _calc_max_drawdown(equity_curve),
            "best_trade":  max(trades, key=lambda t: t["pnl"], default=None),
            "worst_trade": min(trades, key=lambda t: t["pnl"], default=None),
        },
        "trades": trades, "equity_curve": equity_curve,
    }


@router.get("/run-asia")
def run_backtest_asia(
    symbol:           str = Query(default="NQ=F"),
    instrument:       str = Query(default="MNQ"),
    lookback_days:    int = Query(default=30, ge=5, le=90),
    contracts:        int = Query(default=1, ge=1, le=20),
    daily_loss_limit: int = Query(default=1000),
):
    """
    Asia/Overnight session backtest (7:00 PM – 10:30 PM ET).
    NQ Asia session follows direction set by US close + overnight futures sentiment.
    """
    return _run_session_backtest(
        symbol=symbol, instrument=instrument,
        lookback_days=lookback_days, contracts=contracts,
        daily_loss_limit=daily_loss_limit,
        kz_start=(19, 0), kz_end=(22, 30),
        session_label="Asia",
        start_bar_index=3,
    )


@router.get("/run-gold-asia")
def run_backtest_gold_asia(
    instrument:       str = Query(default="MGC"),
    lookback_days:    int = Query(default=30, ge=5, le=90),
    contracts:        int = Query(default=1, ge=1, le=20),
    daily_loss_limit: int = Query(default=1000),
):
    """
    Gold (MGC) Asia/London Open session backtest (2:00 AM – 5:30 AM ET).
    Gold is most reactive during Tokyo/London overlap — best sweep setups occur here.
    """
    return _run_session_backtest(
        symbol="GC=F", instrument=instrument,
        lookback_days=lookback_days, contracts=contracts,
        daily_loss_limit=daily_loss_limit,
        kz_start=(2, 0), kz_end=(5, 30),
        session_label="Gold Asia/London",
        start_bar_index=3,
    )


# ── TEST ENDPOINT — experimental filters, Arlennys base, 1h extended history ──
#
# /api/backtest/run-test is a sandbox copy of run_backtest.
# The production /api/backtest/run endpoint (Arlennys Model) is NEVER modified here.
# New concepts from coach transcripts are added to this endpoint only.
# Supports 1h interval → up to 730-day lookback for large sample sizes.

def _download_1h(symbol: str, lookback_days: int) -> list:
    """Download up to 720 days of 1h bars for extended backtesting."""
    end_dt   = datetime.now(tz=UTC)
    start_dt = end_dt - timedelta(days=min(lookback_days + 3, 720))
    try:
        import yfinance as yf
        df = yf.download(symbol, start=start_dt, end=end_dt,
                         interval="1h", progress=False, auto_adjust=True)
        return _parse_bars(df, symbol)
    except Exception:
        return []


@router.get("/run-test")
def run_backtest_test(
    symbol:           str   = Query(default="NQ=F"),
    instrument:       str   = Query(default="MNQ"),
    lookback_days:    int   = Query(default=90,   ge=5, le=720),
    contracts:        int   = Query(default=1,    ge=1, le=20),
    daily_loss_limit: int   = Query(default=1000, ge=100, le=5000),
    interval:         str   = Query(default="1h", description="1h (730d max) or 5m (90d max)"),
    # ── Arlennys base thresholds (override to test) ───────────────────────────
    score_tue_thu:    int   = Query(default=65,   ge=30, le=100),
    score_mon:        int   = Query(default=70,   ge=30, le=100),
    score_fri:        int   = Query(default=68,   ge=30, le=100),
    vol_regime_pct:   float = Query(default=4.0,  ge=1.0, le=15.0),
    atr_stop_cap:     float = Query(default=120.0,ge=20.0, le=500.0),
    require_mss:      int   = Query(default=1,    ge=0, le=1),
    # ── Experimental flags (set via transcript concepts) ─────────────────────
    # Each flag defaults OFF — only activate when a transcript concept is added
    exp_vwap_slope:   int   = Query(default=0, ge=0, le=1,
                                    description="Require rising VWAP slope for longs, falling for shorts"),
    exp_entry_volume: int   = Query(default=0, ge=0, le=1,
                                    description="Require entry bar volume > 0.8x session average"),
    exp_or30_required:int   = Query(default=0, ge=0, le=1,
                                    description="Require OR30 breakout before ICT entry (5m only)"),
    # ── Korabi Trades concepts ────────────────────────────────────────────────
    exp_smt_confirm:  int   = Query(default=0, ge=0, le=1,
                                    description="Require SMT divergence (NQ+ES disagree) in trade direction"),
    exp_ext_liq:      int   = Query(default=0, ge=0, le=1,
                                    description="Require external liquidity sweep (EQH/EQL/session level, not just intraday)"),
    exp_bpr_entry:    int   = Query(default=0, ge=0, le=1,
                                    description="Require BPR zone (overlapping bull+bear FVGs at entry)"),
    exp_tight_stop:   int   = Query(default=0, ge=0, le=1,
                                    description="Hard cap stop at 50pts MNQ / 25pts MES (Korabi precision entries)"),
):
    """
    Test sandbox for new strategy concepts.
    Base = Arlennys Model. Add experimental flags one at a time and compare.
    Use interval=1h for 730-day lookback (statistical confidence).
    Use interval=5m for precise entry-level backtesting (90d max).
    """
    use_1h = (interval == "1h")
    if use_1h:
        bars_all = _download_1h(symbol, lookback_days)
    else:
        end_dt   = datetime.now(tz=UTC)
        start_dt = end_dt - timedelta(days=min(lookback_days + 3, 93))
        bars_all = _download(symbol, start_dt, end_dt + timedelta(hours=2), "5m")

    if not bars_all:
        return {"error": f"No data for {symbol} at {interval}"}

    config     = _INSTRUMENT_CONFIG.get(instrument.upper(), _INSTRUMENT_CONFIG["MNQ"])
    usd_per_pt = config["dollars_per_point"] * contracts

    # Daily bars for HTF bias (always 1d regardless of test interval)
    end_dt_htf   = datetime.now(tz=UTC)
    daily_bars_all = _download(symbol, end_dt_htf - timedelta(days=90), end_dt_htf, "1d")

    # ES bars for SMT divergence (download only when flag is active to save time)
    es_bars_all: list = []
    if exp_smt_confirm:
        es_sym = "ES=F" if symbol == "NQ=F" else "NQ=F"
        if use_1h:
            es_bars_all = _download_1h(es_sym, lookback_days)
        else:
            end_dt_es = datetime.now(tz=UTC)
            es_bars_all = _download(es_sym, end_dt_es - timedelta(days=min(lookback_days+3, 93)),
                                    end_dt_es + timedelta(hours=2), "5m")
    es_by_day = _group_by_day(es_bars_all) if es_bars_all else {}

    by_day        = _group_by_day(bars_all)
    trades        = []
    running_pnl   = 0.0
    equity_curve  = []
    days_sorted   = sorted(by_day.keys())

    for i, d in enumerate(days_sorted):
        if d.weekday() >= 5:
            continue

        day_bars   = by_day[d]
        prior_bars = []
        for pd in days_sorted[:i]:
            prior_bars.extend(by_day[pd])
        prior_bars = prior_bars[-300:]

        htf_bars   = [b for b in daily_bars_all if b["time"][:10] < d.isoformat()]
        htf_result = get_htf_bias(htf_bars) if len(htf_bars) >= 22 else {"bias": "neutral"}
        htf_dir    = htf_result.get("bias", "neutral")

        is_monday = d.weekday() == 0
        is_friday = d.weekday() == 4
        day_min_score = score_mon if is_monday else score_fri if is_friday else score_tue_thu

        prior_map     = {pd: by_day[pd] for pd in days_sorted[:i]}
        used_entries: list = []
        day_traded    = False
        trades_today  = 0
        next_bar_idx  = 1 if use_1h else 6  # 1h killzone has fewer bars

        while trades_today < 2:
            # ── Experimental: VWAP slope filter ───────────────────────────────
            # If enabled, compute slope of VWAP over last 2 1h bars before entry;
            # skip longs when VWAP is declining, skip shorts when rising.
            # Implemented inside _find_killzone_setup via extra pre-check for now.

            setup = _find_killzone_setup(
                day_bars, prior_bars,
                instrument=instrument.upper(),
                start_bar_index=next_bar_idx,
                htf_direction=htf_dir,
                used_entries=used_entries,
                kz_start=(9, 30), kz_end=(11, 30),
                prior_days=prior_map,
                min_score=day_min_score,
                sweep_max_age_mins=180 if use_1h else 90,
                require_mss=bool(require_mss),
                vol_regime_pct=vol_regime_pct,
                min_kz_bars=2 if use_1h else 6,
                session_vwap_start=570 if use_1h else 0,
                fvg_prox_mult=12.0 if use_1h else 3.0,
                atr_min_mult=0.0 if use_1h else 2.0,
            )

            if not setup:
                break

            bar_dt = _bar_dt(setup["entry_bar"])

            # ── Experimental: VWAP slope ──────────────────────────────────────
            if exp_vwap_slope:
                vwap_now  = _calc_vwap_at(day_bars, bar_dt)
                look_back = bar_dt - timedelta(minutes=60 if use_1h else 30)
                vwap_prev = _calc_vwap_at(day_bars, look_back)
                if vwap_now and vwap_prev:
                    slope_up   = vwap_now > vwap_prev
                    slope_down = vwap_now < vwap_prev
                    if setup["direction"] == "bullish" and not slope_up:
                        next_bar_idx = setup["bar_index"] + 1
                        continue
                    if setup["direction"] == "bearish" and not slope_down:
                        next_bar_idx = setup["bar_index"] + 1
                        continue

            # ── Experimental: entry-bar volume ────────────────────────────────
            if exp_entry_volume:
                entry_vol = setup["entry_bar"].get("volume", 0) or 0
                session_bars_so_far = [
                    b for b in day_bars
                    if 9 * 60 + 30 <= _bar_dt(b).hour * 60 + _bar_dt(b).minute <= 11 * 60 + 30
                ]
                avg_sess_vol = (sum(b.get("volume", 0) or 0 for b in session_bars_so_far)
                                / max(len(session_bars_so_far), 1))
                if avg_sess_vol > 0 and entry_vol < avg_sess_vol * 0.8:
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Experimental: OR30 required before ICT entry ──────────────────
            if exp_or30_required and not use_1h:
                if not _check_or30_breakout(day_bars, setup["direction"], bar_dt):
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Korabi: SMT divergence required ──────────────────────────────
            # Concept: A+ entries happen when NQ and ES diverge at the same level.
            # NQ sweeps a swing and ES holds (or vice versa) = institutional accumulation.
            if exp_smt_confirm:
                _kz_ctx  = (prior_bars + day_bars)[-200:]
                _sl      = extract_session_levels(_kz_ctx, reference_dt=bar_dt)
                _ehl     = detect_equal_highs_lows(_kz_ctx)
                # Secondary bars: ES on same day window
                _es_day  = es_by_day.get(d, [])
                _es_prior: list = []
                for _pd in days_sorted[:i]:
                    _es_prior.extend(es_by_day.get(_pd, []))
                _es_ctx  = (_es_prior + _es_day)[-200:]
                _adv = get_advanced_signals(bars=_kz_ctx, session_levels=_sl,
                                            equal_hl=_ehl, bars_secondary=_es_ctx,
                                            bias_direction=setup["direction"])
                smt = _adv.get("smt_divergence") or {}
                if not (smt.get("detected") or smt.get("divergence_detected")):
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Korabi: External liquidity sweep required ─────────────────────
            # Concept: IRL→ERL — price must have swept an external (major) level
            # like EQH, EQL, prev session H/L, or a multi-day swing.
            # Internal sweeps (intraday micro-levels) don't qualify.
            if exp_ext_liq:
                sweep_label = (setup.get("sweep_label") or "").lower()
                is_external = any(kw in sweep_label for kw in
                                  ("eqh", "eql", "equal", "prev", "session", "asia", "london",
                                   "week", "month", "swing", "bsl", "ssl"))
                if not is_external:
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Korabi: BPR (Balanced Price Range) at entry zone ─────────────
            # Concept: Two overlapping opposing FVGs create a premium/discount zone.
            # Entry inside this zone = high-probability because both buy-side and
            # sell-side inefficiency cancel out at that price.
            if exp_bpr_entry:
                _kz_ctx2 = (prior_bars + day_bars)[-200:]
                all_fvgs  = detect_fvg(_kz_ctx2)
                bull_fvgs = [f for f in all_fvgs if f.get("type") == "bullish_fvg" and not f.get("filled")]
                bear_fvgs = [f for f in all_fvgs if f.get("type") == "bearish_fvg" and not f.get("filled")]
                bpr_found = False
                for bf in bull_fvgs:
                    for brf in bear_fvgs:
                        overlap_lo = max(bf.get("bottom", 0), brf.get("bottom", 0))
                        overlap_hi = min(bf.get("top", 0),    brf.get("top",    0))
                        if overlap_hi > overlap_lo and overlap_lo <= setup["entry"] <= overlap_hi:
                            bpr_found = True
                            break
                    if bpr_found:
                        break
                if not bpr_found:
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Korabi: Tight stop — precision entry only ─────────────────────
            # Concept: Korabi uses 13-20pt stops on NQ (vs Arlennys 50-120pt).
            # Only accept setups where the natural stop is ≤ 50pts MNQ.
            if exp_tight_stop:
                tight_cap = {"MNQ": 50.0, "MES": 25.0, "MGC": 6.0}.get(instrument.upper(), 50.0)
                if setup["stop_dist"] > tight_cap:
                    next_bar_idx = setup["bar_index"] + 1
                    continue

            # ── Apply ATR stop cap override ───────────────────────────────────
            if setup["stop_dist"] > atr_stop_cap:
                next_bar_idx = setup["bar_index"] + 1
                continue

            outcome = _simulate_trade(
                setup["entry"], setup["stop"], setup["target"],
                setup["direction"], setup["remaining_bars"],
                stop_dist=setup["stop_dist"],
            )
            res  = outcome["result"]
            sd   = setup["stop_dist"]

            if res == "win":
                pts = (outcome["exit_price"] - setup["entry"]) if setup["direction"] == "bullish" \
                      else (setup["entry"] - outcome["exit_price"])
            elif res == "partial_win":
                pts = sd * 0.5
            else:
                pts = (outcome["exit_price"] - setup["entry"]) if setup["direction"] == "bullish" \
                      else (setup["entry"] - outcome["exit_price"])

            pnl = round(pts * usd_per_pt, 2)
            running_pnl += pnl
            day_traded   = True
            trades_today += 1
            used_entries.append(setup["entry"])
            next_bar_idx = setup["bar_index"] + 2

            session_label = "TEST" if trades_today == 1 else "TEST2"
            trades.append({
                "date": d.isoformat(), "day": d.strftime("%a %b %d"),
                "session": session_label, "direction": setup["direction"],
                "grade": setup["grade"], "score": setup["score"],
                "htf_dir": htf_dir,
                "entry": setup["entry"], "stop": setup["stop"],
                "target": setup["target"], "exit_price": outcome["exit_price"],
                "result": res, "eod": outcome.get("eod", False),
                "pts": round(pts, 2), "pnl": pnl,
                "rr_achieved": round(pts / sd, 2) if sd else 0,
                "rr_planned": setup["rr_ratio"], "stop_dist": sd,
                "sweep": setup["sweep_label"], "fvg_zone": setup["fvg_zone"],
                "dol": setup["dol_reason"], "running_pnl": round(running_pnl, 2),
            })
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": True})

            if res == "loss":
                break

        if not day_traded:
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": False})

    wins   = [t for t in trades if t["result"] in ("win", "partial_win")]
    losses = [t for t in trades if t["result"] == "loss"]
    total  = len(trades)
    win_rate = round(len(wins) / total * 100, 1) if total else 0
    avg_win  = round(sum(t["pnl"] for t in wins)   / len(wins),   2) if wins   else 0
    avg_loss = round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0
    pf       = round(abs(sum(t["pnl"] for t in wins)) /
                     max(abs(sum(t["pnl"] for t in losses)), 0.01), 2)
    avg_rr   = round(sum(t["rr_achieved"] for t in trades) / total, 2) if total else 0
    monthly_projection = round(running_pnl / max(lookback_days, 1) * 21, 2)

    # Breakdown by month
    monthly: dict = {}
    for t in trades:
        m = t["date"][:7]
        monthly.setdefault(m, {"trades": 0, "wins": 0, "pnl": 0.0})
        monthly[m]["trades"] += 1
        if t["result"] in ("win", "partial_win"):
            monthly[m]["wins"] += 1
        monthly[m]["pnl"] += t["pnl"]

    return {
        "symbol": symbol, "instrument": instrument.upper(),
        "interval": interval, "contracts": contracts,
        "lookback_days": lookback_days,
        "flags": {
            "exp_vwap_slope":    bool(exp_vwap_slope),
            "exp_entry_volume":  bool(exp_entry_volume),
            "exp_or30_required": bool(exp_or30_required),
            "exp_smt_confirm":   bool(exp_smt_confirm),
            "exp_ext_liq":       bool(exp_ext_liq),
            "exp_bpr_entry":     bool(exp_bpr_entry),
            "exp_tight_stop":    bool(exp_tight_stop),
        },
        "stats": {
            "total_trades": total, "wins": len(wins), "losses": len(losses),
            "eod_closes":   len([t for t in trades if t.get("eod")]),
            "win_rate": win_rate, "total_pnl": round(running_pnl, 2),
            "monthly_projection": monthly_projection,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "profit_factor": pf, "avg_rr": avg_rr,
            "max_drawdown": _calc_max_drawdown(equity_curve),
            "best_trade":  max(trades, key=lambda t: t["pnl"], default=None),
            "worst_trade": min(trades, key=lambda t: t["pnl"], default=None),
        },
        "monthly_breakdown": {
            m: {**v, "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0}
            for m, v in sorted(monthly.items())
        },
        "trades": trades,
        "equity_curve": equity_curve,
    }
