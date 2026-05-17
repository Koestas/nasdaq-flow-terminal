"""Learn / practice mode — replay historical bars with ICT coaching."""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta
import pytz
import yfinance as yf

from engines.ict import (get_ict_analysis, extract_session_levels,
                         detect_equal_highs_lows)
from engines.ict_signals import get_advanced_signals

router = APIRouter(prefix="/api/learn", tags=["learn"])

NY_TZ = pytz.timezone("America/New_York")
VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "1h"}


# ── Data helpers ─────────────────────────────────────────────────────────────

def _download_bars(symbol: str, start: datetime, end: datetime, interval: str) -> list:
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
                o = float(row["Open"])  or None
                h = float(row["High"])  or None
                l = float(row["Low"])   or None
                c = float(row["Close"]) or None
                v = float(row.get("Volume") or 0)
            except Exception:
                continue
            if None in (o, h, l, c):
                continue
            bars.append({
                "time":   ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open":   round(o, 4), "high": round(h, 4),
                "low":    round(l, 4), "close": round(c, 4), "volume": v or 0,
            })
        return bars
    except Exception:
        return []


def _filter_until(bars: list, end_dt: datetime) -> list:
    """Keep bars with timestamp ≤ end_dt."""
    result = []
    end_aware = end_dt if end_dt.tzinfo else end_dt.replace(tzinfo=pytz.UTC)
    for b in bars:
        try:
            ts_str = b["time"].replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=pytz.UTC)
            if ts <= end_aware:
                result.append(b)
        except Exception:
            continue
    return result


# ── Coaching narrative ────────────────────────────────────────────────────────

def _sweep_quality(sweep: dict, symbol: str) -> str:
    """Grade a liquidity sweep: clean (tight wick), aggressive, or thin."""
    level  = sweep.get("level") or 0
    wick   = sweep.get("wick_low") or sweep.get("wick_high") or level
    dist   = abs(wick - level)
    # GC=F trades in $-per-oz; equities/QQQ in proxy pts
    if "GC" in symbol or "GC=F" in symbol:
        if dist < 0.50:   return "thin"
        if dist <= 5.0:   return "clean"
        return "aggressive"
    else:
        if dist < 0.03:   return "thin"
        if dist <= 0.40:  return "clean"
        return "aggressive"


def _ifvg_status(ifvg: dict, price: float) -> str:
    """Describe where current price is relative to an iFVG zone (direction-aware)."""
    top    = ifvg.get("top")    or 0
    bottom = ifvg.get("bottom") or 0
    mid    = ifvg.get("mid")    or (top + bottom) / 2
    is_bull = "bullish" in (ifvg.get("base_type") or "")

    if is_bull:
        # Bullish iFVG = support zone; entry when price comes down to it
        if price > top:
            return "above zone — not yet tapped"
        if price < bottom:
            return "VIOLATED — price closed below zone, reduced confidence"
        if price <= mid:
            return "IN ZONE (below CE) — deep retrace, still valid but tightening"
        return "IN ZONE — ideal entry area"
    else:
        # Bearish iFVG = resistance zone; entry when price rallies into it
        if price < bottom:
            return "below zone — not yet tapped"
        if price > top:
            return "VIOLATED — price closed above zone, reduced confidence"
        if price >= mid:
            return "IN ZONE (above CE) — deep retrace into resistance, valid but tightening"
        return "IN ZONE — ideal short entry area"


def _narrative(analysis: dict, advanced: dict, symbol: str, label: str,
               current_price: float = None) -> str:
    sess      = analysis.get("session") or {}
    po3       = advanced.get("po3_phase") or {}
    sweeps    = advanced.get("liquidity_sweeps") or []
    dol       = analysis.get("draw_on_liquidity") or {}
    dp        = analysis.get("discount_premium") or {}
    ifvgs     = [f for f in (analysis.get("fair_value_gaps", []) or []) if f.get("inverted")]
    raw_fvgs  = [f for f in (analysis.get("fair_value_gaps", []) or [])
                 if not f.get("filled") and not f.get("inverted")]
    mss       = advanced.get("mss_choch") or {}
    ote       = advanced.get("ote_zone") or {}
    in_ote    = advanced.get("in_ote", False)
    smt       = advanced.get("smt_divergence") or {}
    long_s    = analysis.get("long_setup", {})
    short_s   = analysis.get("short_setup", {})
    long_sc   = long_s.get("score", 0)
    short_sc  = short_s.get("score", 0)
    bias      = "bullish" if long_sc > short_sc else "bearish" if short_sc > long_sc else "neutral"
    in_kz     = sess.get("in_killzone", False)
    session   = sess.get("session", "Unknown")
    price     = current_price or (analysis.get("fair_value_gaps") or [{}])[-1].get("top", 0)

    # ET hour for first-15-min blackout check
    try:
        import pytz as _tz
        _et = _tz.timezone("America/New_York")
        _now = _tz.utc.localize(__import__("datetime").datetime.utcnow()).astimezone(_et)
        in_first15 = (_now.hour == 9 and _now.minute < 45)
    except Exception:
        in_first15 = False

    # Derived helpers
    dol_dir    = dol.get("direction", "neutral")
    dol_target = dol.get("target", "?")
    dol_reason = dol.get("reason", "")
    arrow      = "↑" if dol_dir == "up" else "↓" if dol_dir == "down" else "→"
    zone       = dp.get("zone", "")
    pos        = dp.get("position_pct")
    struct     = mss.get("last_structure", "unknown")
    recent_sw  = [s for s in sweeps if s.get("direction") in ("bullish", "bearish")][-5:]
    last_sw    = recent_sw[-1] if recent_sw else None

    # Zone alignment check
    zone_aligned = (zone == "discount" and dol_dir == "up") or (zone == "premium" and dol_dir == "down")

    L = []
    L.append(f"─── ICT COACH: {label} on {symbol} ───")
    L.append("")

    # ── 1. BIAS (top-down framework) ──────────────────────────────────────────
    L.append("BIAS (Multi-Timeframe):")
    if bias == "bullish":
        # Find the nearest bearish FVG above price — that's the invalidation
        bear_above = [f for f in raw_fvgs if f.get("base_type") == "bearish_fvg"
                      and (f.get("bottom") or 0) > price]
        inv_level = bear_above[0]["bottom"] if bear_above else None
        L.append(f"  BULLISH — I am LONG-biased until price fills the bearish FVG"
                 + (f" at {inv_level:.2f}" if inv_level else " above current price"))
        L.append(f"  Read 4H → 1H → 30m all confirm upside draw; use 5m/15m for entry")
    elif bias == "bearish":
        bull_below = [f for f in raw_fvgs if f.get("base_type") == "bullish_fvg"
                      and (f.get("top") or 0) < price]
        inv_level = bull_below[-1]["top"] if bull_below else None
        L.append(f"  BEARISH — I am SHORT-biased until price fills the bullish FVG"
                 + (f" at {inv_level:.2f}" if inv_level else " below current price"))
        L.append(f"  Read 4H → 1H → 30m all confirm downside draw; use 5m/15m for entry")
    else:
        L.append("  NEUTRAL — Long and short scores equal. No trade until bias resolves.")
        L.append("  Look at the 1H chart: which FVG has price NOT yet returned to fill?")

    L.append("")

    # ── 2. SESSION + AMD PHASE ────────────────────────────────────────────────
    L.append("SESSION & AMD PHASE:")
    kz_tag = " [KILLZONE ACTIVE]" if in_kz else ""
    L.append(f"  {session}{kz_tag}")
    if po3.get("phase_label"):
        phase = po3["phase_label"]
        desc  = po3.get("description", "")
        amd_map = {
            "Accumulation": "Price is coiling — mark levels, DO NOT trade yet. Wait for the sweep.",
            "Manipulation": "SWEEP PHASE — this is the stop-hunt. Watch the next few candles for displacement and a FVG to form.",
            "Distribution":  "DELIVERY — price is moving to the target. Trail your stop, don't exit early on small wicks.",
        }
        friendly = amd_map.get(phase, desc)
        L.append(f"  PO3: {phase} — {friendly}")

    L.append("")

    # ── 3. ZONE & DOL ─────────────────────────────────────────────────────────
    L.append("PRICE LOCATION:")
    if zone and pos is not None:
        badge = "✓ ALIGNED" if zone_aligned else "✗ MISALIGNED"
        L.append(f"  Zone: {zone.upper()} ({pos:.1f}% of daily range) — DOL {badge}")
        if not zone_aligned:
            L.append(f"  NOTE: Longs from DISCOUNT, Shorts from PREMIUM. "
                     f"{'Wait for a deeper pullback.' if bias=='bullish' else 'Wait for a rally into premium.'}")
    if dol_dir != "neutral":
        L.append(f"  Draw on Liquidity: {arrow} {dol_target} ({dol_reason})")
    else:
        L.append("  Draw on Liquidity: Unclear — no dominant liquidity target yet")

    L.append("")

    # ── 4. SWEEPS ─────────────────────────────────────────────────────────────
    L.append("LIQUIDITY SWEEPS:")
    if recent_sw:
        for sw in reversed(recent_sw[-3:]):
            sq = _sweep_quality(sw, symbol)
            quality_tag = {
                "clean":      " ✓ CLEAN SWEEP (tight wick, high quality)",
                "aggressive": " ⚠ AGGRESSIVE sweep (large wick — lower quality, proceed with caution)",
                "thin":       " ⚠ THIN sweep (barely past level — may not be enough to sweep stops)",
            }[sq]
            L.append(f"  • {sw.get('direction','?').upper()} sweep of {sw.get('label','?')}"
                     + quality_tag)
            if sq == "aggressive":
                L.append("    → Very large wick = could be manipulation OF the manipulation. "
                         "Wait for the iFVG and make sure structure confirms direction.")
    else:
        L.append("  NONE — NO ENTRY until a key level is swept.")
        L.append("  Key levels to watch: Asia H/L, London H/L, PDH/PDL, Equal H/L above/below")

    L.append("")

    # ── 5. iFVGs (entry zones) ────────────────────────────────────────────────
    L.append("iFVG ENTRY ZONES:")
    if ifvgs:
        for f in ifvgs[:3]:
            base = f.get("base_type", "")
            fdir = "BULLISH" if "bullish" in base else "BEARISH"
            status = _ifvg_status(f, price)
            ce_val = f.get("mid", 0)
            L.append(f"  • {fdir} iFVG: {f.get('bottom'):.2f} – {f.get('top'):.2f}  |  CE: {ce_val:.2f}  |  {status}")
            if "VIOLATED" in status:
                L.append("    → CE breached with a close — treat this iFVG as invalid. Find the next one.")
            elif "IN ZONE" in status and "below CE" in status:
                L.append("    → Price is below the CE. Still valid, but trail the stop aggressively. "
                         "If next candle closes below bottom, EXIT.")
            elif "IN ZONE" in status:
                L.append("    → IDEAL ENTRY AREA. Wait for a strong displacement candle away from this zone.")
    else:
        L.append("  NONE — iFVG forms only after: sweep → displacement → FVG fills → price closes back through (V-shape)")
        L.append("  Sequence: sweep a level → watch 1m/2m chart → FVG appears → price re-enters FVG → "
                 "closes ABOVE top (bullish) or BELOW bottom (bearish) = iFVG born")

    # FVG context
    bull_fvg = [f for f in raw_fvgs if f.get("base_type") == "bullish_fvg"]
    bear_fvg = [f for f in raw_fvgs if f.get("base_type") == "bearish_fvg"]
    if bull_fvg or bear_fvg:
        L.append(f"  Unfilled FVGs nearby: {len(bull_fvg)} bullish / {len(bear_fvg)} bearish "
                 f"(price will be drawn to fill these)")

    L.append("")

    # ── 6. STRUCTURE + OTE + SMT ─────────────────────────────────────────────
    L.append("STRUCTURE & CONFLUENCE:")
    L.append(f"  Market Structure: {struct.upper().replace('_',' ')}")
    if in_ote:
        L.append(f"  OTE Zone: ★ PRICE IS IN THE OTE ({ote.get('direction','?')} 0.618–0.786 retracement)")
        L.append("    → This is the highest-probability entry window. OTE + iFVG + sweep = A+ setup.")
    elif ote.get("ote_top") and ote.get("ote_bottom"):
        L.append(f"  OTE Zone: {ote.get('direction','?')} OTE at {ote['ote_bottom']}–{ote['ote_top']} (not yet reached)")
    if smt.get("detected"):
        L.append(f"  SMT: {smt.get('description','')}")
        L.append("    → SMT divergence confirms institutional footprint. This is extra confluence.")

    L.append("")

    # ── 7. ACTION PLAN ────────────────────────────────────────────────────────
    L.append("── WHAT TO DO RIGHT NOW ──")

    if not in_kz:
        L.append(f"  ⛔ OUTSIDE NY KILLZONE ({session})")
        L.append("  → No trade entries. Use this time to:")
        L.append("    1. Mark Asia H/L and London H/L on your chart")
        L.append("    2. Note the nearest Equal Highs/Lows (EQH/EQL)")
        L.append("    3. Identify today's DOL — where is price DRAWN to?")
        L.append("    4. Wait. The killzone opens 9:30 AM ET.")
    elif in_first15:
        L.append("  ⛔ FIRST 15 MINUTES (9:30–9:45 AM ET) — OBSERVE ONLY")
        L.append("  → Never trade the open. The first 15 min is pure manipulation.")
        L.append("  → Watch which direction price sweeps first — that tells you the real move direction.")
    elif not recent_sw:
        L.append("  ⏳ WAITING FOR SWEEP")
        L.append(f"  → We are in the {session} killzone but NO sweep yet.")
        L.append("  → Do NOT chase price. Wait for it to take a key level's liquidity:")
        L.append("    • Asia H/L, London H/L, Previous Day H/L, or Equal H/L cluster")
        L.append("  → If price keeps moving without a sweep = thin air move, skip it entirely.")
    elif last_sw and not ifvgs:
        sq = _sweep_quality(last_sw, symbol)
        sw_dir = last_sw.get("direction", "?")
        L.append(f"  ✓ SWEEP CONFIRMED ({sw_dir.upper()}) — NOW WAIT FOR THE iFVG")
        if sq == "aggressive":
            L.append("  ⚠ The sweep was very large. Be more selective — the iFVG needs to be clean too.")
        L.append("  → Switch to 1m or 2m chart NOW.")
        L.append("  → Watch for: a rapid displacement candle away from the swept level")
        L.append("  → That candle likely leaves a FVG (gap) behind it")
        L.append("  → Wait for price to re-enter that FVG, then look for a V-shape candle closing BACK through:")
        if sw_dir == "bullish":
            L.append("    - Bullish V: price dips into FVG → next candle closes ABOVE the FVG top = long entry")
        else:
            L.append("    - Bearish V: price pops into FVG → next candle closes BELOW the FVG bottom = short entry")
        L.append("  → DO NOT enter on the sweep candle itself. Wait for the iFVG confirmation.")
    elif last_sw and ifvgs:
        best = ifvgs[0]
        status = _ifvg_status(best, price)
        if "VIOLATED" in status:
            L.append("  ⚠ IFVG VIOLATED — Entry zone is no longer valid.")
            L.append("  → Step back. Look for the NEXT iFVG forming on the next displacement leg.")
            L.append("  → Do NOT hold a losing trade hoping it comes back. If iFVG is closed through, exit.")
        elif "IN ZONE" in status:
            fdir = "LONG" if "bullish" in best.get("base_type", "") else "SHORT"
            L.append(f"  ★★★ ENTRY OPPORTUNITY — PRICE IS IN THE iFVG ZONE")
            L.append(f"  → {fdir} SETUP active:")
            L.append(f"     Entry zone: {best.get('bottom'):.2f} – {best.get('top'):.2f}")
            L.append(f"     CE (midpoint): {best.get('mid'):.2f} — watch for a hold above/below CE")
            if fdir == "LONG":
                L.append(f"     Stop: below {best.get('bottom'):.2f} (sweep low + buffer)")
                L.append(f"     Target 1: DOL {arrow} {dol_target}")
                L.append("     Risk: if price CLOSES below CE, tighten stop immediately")
                L.append("     Exit early: if a large bearish candle closes through iFVG bottom")
            else:
                L.append(f"     Stop: above {best.get('top'):.2f} (sweep high + buffer)")
                L.append(f"     Target 1: DOL {arrow} {dol_target}")
                L.append("     Risk: if price CLOSES above CE, tighten stop immediately")
                L.append("     Exit early: if a large bullish candle closes through iFVG top")
            if in_ote:
                L.append("  ★ BONUS: Price is ALSO in the OTE zone — this is an A+ setup")
            if smt.get("detected"):
                L.append("  ★ BONUS: SMT divergence confirmed — institutions are positioned this way")
            if not zone_aligned:
                L.append("  ⚠ Zone misalignment: price not in ideal zone for this trade direction — reduce size")
        else:
            fdir = "long" if "bullish" in best.get("base_type", "") else "short"
            L.append(f"  ⏳ iFVG EXISTS — waiting for price to return to zone")
            L.append(f"  → {fdir.upper()} iFVG zone: {best.get('bottom'):.2f} – {best.get('top'):.2f}")
            L.append("  → Do NOT chase. Let price COME TO YOU. That is the entire edge.")
            L.append("  → If price runs to target without tapping the iFVG = skip, next setup will come.")
    else:
        L.append("  → No clear ICT edge at this moment. Mark your levels and observe.")

    # Fakeout reminder
    L.append("")
    L.append("FAKEOUT PROTECTION:")
    L.append("  • A wick PAST your iFVG bottom (long) / top (short) is normal — watch the CLOSE")
    L.append("  • If price closes through CE with conviction → tighten stop or exit half")
    L.append("  • A sweep that reverses 5+ bars later without iFVG = manipulation of manipulation → skip")
    L.append("  • In a trade and price spikes against you? Check: is this a new sweep of YOUR stop zone?")
    L.append("    If yes → the iFVG is still intact until a CANDLE CLOSES through it")

    L.append("")
    L.append(f"SETUP GRADES: Long {long_s.get('grade','--')} ({long_sc}/100)  |  "
             f"Short {short_s.get('grade','--')} ({short_sc}/100)")

    return "\n".join(L)


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/replay")
async def learn_replay(
    symbol: str = Query(default="QQQ", description="QQQ, SPY, or GC=F"),
    interval: str = Query(default="5m",  description="1m, 5m, 15m, 30m, 1h"),
    end_time: str = Query(default=None,  description="ISO cutoff: 2025-01-15T10:30:00 (ET assumed if no tz)"),
    lookback_days: int = Query(default=5, ge=1, le=30, description="Days of history before end_time"),
):
    if interval not in VALID_INTERVALS:
        interval = "5m"

    # Resolve end_time
    now_utc = datetime.now(tz=pytz.UTC)
    if end_time:
        try:
            parsed = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = NY_TZ.localize(parsed)
            end_dt = parsed.astimezone(pytz.UTC)
        except Exception:
            end_dt = now_utc
    else:
        end_dt = now_utc

    start_dt = end_dt - timedelta(days=lookback_days + 1)

    # Fetch + filter bars
    bars_all = _download_bars(symbol, start_dt, end_dt + timedelta(hours=1), interval)
    bars = _filter_until(bars_all, end_dt)

    if not bars:
        return {"error": "No bar data for that time range", "bars": [], "symbol": symbol,
                "end_time": end_dt.isoformat()}

    # ICT analysis
    price    = bars[-1]["close"]
    analysis = get_ict_analysis(bars, vwap=None, current_price=price)
    session_levels = extract_session_levels(bars)
    equal_hl = detect_equal_highs_lows(bars)

    long_sc  = analysis.get("long_setup",  {}).get("score", 0)
    short_sc = analysis.get("short_setup", {}).get("score", 0)
    bias = ("bullish" if long_sc > short_sc else
            "bearish" if short_sc > long_sc else "neutral")

    # Secondary for SMT
    secondary = "SPY" if symbol == "QQQ" else ("QQQ" if symbol == "SPY" else None)
    bars_sec = []
    if secondary:
        bars_sec_all = _download_bars(secondary, start_dt, end_dt + timedelta(hours=1), interval)
        bars_sec = _filter_until(bars_sec_all, end_dt)

    advanced = get_advanced_signals(
        bars=bars, session_levels=session_levels,
        equal_hl=equal_hl, bars_secondary=bars_sec, bias_direction=bias,
    )

    label     = end_dt.astimezone(NY_TZ).strftime("%Y-%m-%d %I:%M %p ET")
    narrative = _narrative(analysis, advanced, symbol, label, current_price=price)

    return {
        "symbol":        symbol,
        "interval":      interval,
        "end_time":      end_dt.isoformat(),
        "end_time_label": label,
        "current_price": price,
        "bar_count":     len(bars),
        "bars":          bars,
        "session":           analysis.get("session"),
        "session_levels":    session_levels,
        "fvgs":              analysis.get("fair_value_gaps", []),
        "ifvgs":             analysis.get("ifvgs", []),
        "order_blocks":      analysis.get("order_blocks", {}),
        "equal_hl":          equal_hl,
        "discount_premium":  analysis.get("discount_premium", {}),
        "draw_on_liquidity": analysis.get("draw_on_liquidity", {}),
        "long_setup":        analysis.get("long_setup", {}),
        "short_setup":       analysis.get("short_setup", {}),
        "mss_choch":         advanced.get("mss_choch", {}),
        "liquidity_sweeps":  advanced.get("liquidity_sweeps", []),
        "ote_zone":          advanced.get("ote_zone", {}),
        "in_ote":            advanced.get("in_ote", False),
        "ipda_levels":       advanced.get("ipda_levels", {}),
        "smt_divergence":    advanced.get("smt_divergence", {}),
        "po3_phase":         advanced.get("po3_phase", {}),
        "coaching_narrative": narrative,
    }
