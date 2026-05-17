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
                         detect_equal_highs_lows, detect_fvg)
from engines.ict_signals import get_advanced_signals, _INSTRUMENT_CONFIG

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

NY_TZ   = pytz.timezone("America/New_York")
UTC     = pytz.UTC
KZ_START = (9, 30)   # NY time
KZ_END   = (11, 30)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _download(symbol: str, start: datetime, end: datetime, interval: str) -> list:
    try:
        df = yf.download(symbol, start=start, end=end, interval=interval,
                         progress=False, auto_adjust=True)
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
    except Exception:
        return []


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

def _simulate_trade(entry_price: float, stop: float, target: float,
                    direction: str, forward_bars: list) -> dict:
    """Walk forward bars; return which level was hit first."""
    for b in forward_bars:
        h, l = b.get("high", 0), b.get("low", 0)
        if direction == "bullish":
            if l <= stop:
                return {"result": "loss", "exit_price": stop}
            if h >= target:
                return {"result": "win",  "exit_price": target}
        else:
            if h >= stop:
                return {"result": "loss", "exit_price": stop}
            if l <= target:
                return {"result": "win",  "exit_price": target}
    last = forward_bars[-1]["close"] if forward_bars else entry_price
    return {"result": "expired", "exit_price": last}


# ── Per-day signal detection ──────────────────────────────────────────────────

def _find_killzone_setup(day_bars: list, all_prior_bars: list, instrument: str = "MNQ", start_bar_index: int = 6) -> dict | None:
    """
    Walk through the NY killzone bars one at a time; return the first
    A or A+ setup with a sweep + iFVG. Accepts a start_bar_index so
    a second attempt can skip past the first setup's entry bar.
    Returns None if no qualifying setup found.
    """
    kz_bars = [
        b for b in day_bars
        if KZ_START[0] * 60 + KZ_START[1]
           <= _bar_dt(b).hour * 60 + _bar_dt(b).minute
           <= KZ_END[0] * 60 + KZ_END[1]
    ]
    if len(kz_bars) < 6:
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

        adv = get_advanced_signals(
            bars=context, session_levels=sl, equal_hl=ehl,
            bars_secondary=[], bias_direction=bias,
        )

        sweeps = adv.get("liquidity_sweeps") or []
        recent = [s for s in sweeps if s.get("direction") == bias]
        if not recent:
            continue

        ifvgs = analysis.get("ifvgs") or []
        aligned = [f for f in ifvgs
                   if f.get("base_type") == f"{'bullish' if bias=='bullish' else 'bearish'}_fvg"]
        if not aligned:
            continue

        setup_score = long_sc if bias == "bullish" else short_sc
        grade = ("A+" if setup_score >= 80 else
                 "A"  if setup_score >= 60 else
                 "B"  if setup_score >= 40 else "C")
        if grade not in ("A+", "A"):
            continue

        # Build entry / stop / target in price units
        fvg     = min(aligned, key=lambda f: abs(f["mid"] - price))
        entry   = fvg["bottom"] if bias == "bullish" else fvg["top"]
        config  = _INSTRUMENT_CONFIG.get(instrument, _INSTRUMENT_CONFIG["MNQ"])
        buf     = config["stop_buffer"]
        min_st  = config["min_stop_pts"]

        # Skip stale FVGs — price must be near the zone (within 3× the gap size)
        if abs(price - fvg["mid"]) > fvg["size"] * 3 + min_st:
            continue

        if bias == "bullish":
            raw_stop = (min(recent[-1].get("wick_low", recent[-1]["level"]),
                           fvg["bottom"]) - buf)
            stop    = min(raw_stop, entry - min_st)
        else:
            raw_stop = (max(recent[-1].get("wick_high", recent[-1]["level"]),
                           fvg["top"]) + buf)
            stop    = max(raw_stop, entry + min_st)

        stop_dist = abs(entry - stop)
        dol       = analysis.get("draw_on_liquidity") or {}
        dol_tgt   = dol.get("target")
        if dol_tgt and abs(dol_tgt - entry) > stop_dist:
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
async def run_backtest(
    symbol:        str = Query(default="NQ=F", description="NQ=F, ES=F, or GC=F"),
    instrument:    str = Query(default="MNQ"),
    lookback_days: int = Query(default=30, ge=5, le=60),
):
    config     = _INSTRUMENT_CONFIG.get(instrument.upper(), _INSTRUMENT_CONFIG["MNQ"])
    usd_per_pt = config["dollars_per_point"]

    end_dt   = datetime.now(tz=UTC)
    start_dt = end_dt - timedelta(days=lookback_days + 3)

    bars_all = _download(symbol, start_dt, end_dt + timedelta(hours=2), "5m")
    if not bars_all:
        return {"error": f"No data returned for {symbol}"}

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

        # Daily limit: 1 win = done; 2nd loss = done. Max 2 attempts per day.
        day_losses  = 0
        next_start  = 6   # bar index to resume search from
        day_traded  = False

        while day_losses < 2:
            setup = _find_killzone_setup(day_bars, prior_bars,
                                         instrument=instrument.upper(),
                                         start_bar_index=next_start)
            if not setup:
                break

            outcome = _simulate_trade(
                setup["entry"], setup["stop"], setup["target"],
                setup["direction"], setup["remaining_bars"],
            )

            pts = (outcome["exit_price"] - setup["entry"]) if setup["direction"] == "bullish" \
                  else (setup["entry"] - outcome["exit_price"])
            pnl = round(pts * usd_per_pt, 2)
            running_pnl += pnl
            day_traded = True

            trade = {
                "date":        d.isoformat(),
                "day":         d.strftime("%a %b %d"),
                "direction":   setup["direction"],
                "grade":       setup["grade"],
                "score":       setup["score"],
                "entry":       setup["entry"],
                "stop":        setup["stop"],
                "target":      setup["target"],
                "exit_price":  outcome["exit_price"],
                "result":      outcome["result"],
                "pts":         round(pts, 2),
                "pnl":         pnl,
                "rr_achieved": round(pts / setup["stop_dist"], 2) if setup["stop_dist"] else 0,
                "rr_planned":  setup["rr_ratio"],
                "sweep":       setup["sweep_label"],
                "fvg_zone":    setup["fvg_zone"],
                "dol":         setup["dol_reason"],
                "running_pnl": round(running_pnl, 2),
            }
            trades.append(trade)
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": True})

            if outcome["result"] == "win":
                break  # protected the day — stop trading
            elif outcome["result"] == "loss":
                day_losses += 1
                next_start = setup["bar_index"] + 1  # resume search after this bar
            else:
                # expired = killzone ended without resolution — no second attempt
                break

        if not day_traded:
            equity_curve.append({"date": d.isoformat(), "pnl": round(running_pnl, 2), "trade": False})

    # ── Statistics ────────────────────────────────────────────────────────────
    wins   = [t for t in trades if t["result"] == "win"]
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

    return {
        "symbol":        symbol,
        "instrument":    instrument.upper(),
        "lookback_days": lookback_days,
        "trading_days":  len([d for d in days_sorted if by_day[d][0] if d.weekday() < 5]),
        "stats": {
            "total_trades":   total,
            "wins":           len(wins),
            "losses":         len(losses),
            "expired":        len([t for t in trades if t["result"] == "expired"]),
            "win_rate":       win_rate,
            "total_pnl":      round(running_pnl, 2),
            "avg_win":        avg_win,
            "avg_loss":       avg_loss,
            "profit_factor":  pf,
            "avg_rr":         avg_rr,
            "max_drawdown":   max_drawdown,
            "best_trade":     best_trade,
            "worst_trade":    worst_trade,
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
