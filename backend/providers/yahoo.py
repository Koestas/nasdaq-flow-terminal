"""Yahoo Finance data provider via yfinance."""
import math
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
from typing import Optional


LEADERSHIP = ["QQQ", "SPY", "NVDA", "MSFT", "AAPL", "META", "AMD", "TSLA", "AMZN", "SOXX"]

# Approximate Nasdaq-100 weights for leadership scoring
NASDAQ_WEIGHTS = {
    "NVDA": 0.085, "MSFT": 0.08, "AAPL": 0.075, "AMZN": 0.055,
    "META": 0.05, "TSLA": 0.035, "AMD": 0.015, "SOXX": 0.04,
    "QQQ": 0.10, "SPY": 0.05,
}

TECH9_TICKERS = [
    ("NVDA", "Nvidia"),
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Google"),
    ("TSLA", "Tesla"),
    ("WMT", "Walmart"),
    ("META", "Meta"),
    ("AVGO", "Broadcom"),
]


def _clean(val):
    """Return None for NaN/Inf, else val."""
    if val is None:
        return None
    try:
        if math.isnan(val) or math.isinf(val):
            return None
    except TypeError:
        pass
    return val


def _fmt_premium(val: Optional[float]) -> str:
    if val is None:
        return "--"
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:.1f}K"
    return f"${val:.2f}"


def get_qqq_price() -> dict:
    ticker = yf.Ticker("QQQ")
    info = ticker.fast_info
    try:
        price = _clean(float(info.last_price))
        prev_close = _clean(float(info.previous_close))
        day_high = _clean(float(info.day_high))
        day_low = _clean(float(info.day_low))
        volume = _clean(float(info.three_month_average_volume or 0))
    except Exception:
        price = prev_close = day_high = day_low = volume = None

    change = None
    change_pct = None
    if price and prev_close and prev_close != 0:
        change = round(price - prev_close, 2)
        change_pct = round((price - prev_close) / prev_close * 100, 2)

    return {
        "symbol": "QQQ",
        "price": price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "day_high": day_high,
        "day_low": day_low,
        "volume": volume,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_vwap(ticker: str = "QQQ") -> Optional[float]:
    """Calculate VWAP from today's 5-minute bars."""
    try:
        df = yf.download(ticker, period="1d", interval="5m", progress=False, auto_adjust=True)
        if df.empty:
            return None
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical_price * df["Volume"]).cumsum() / df["Volume"].cumsum()
        return _clean(float(vwap.iloc[-1]))
    except Exception:
        return None


def get_intraday(ticker: str = "QQQ", interval: str = "5m") -> list:
    """Return today's intraday OHLCV bars."""
    try:
        df = yf.download(ticker, period="1d", interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return []
        df = df.reset_index()
        bars = []
        for _, row in df.iterrows():
            bars.append({
                "time": row["Datetime"].isoformat() if hasattr(row["Datetime"], "isoformat") else str(row["Datetime"]),
                "open": _clean(float(row["Open"])),
                "high": _clean(float(row["High"])),
                "low": _clean(float(row["Low"])),
                "close": _clean(float(row["Close"])),
                "volume": _clean(float(row["Volume"])),
            })
        return bars
    except Exception:
        return []


def get_options_chain(ticker: str = "QQQ") -> dict:
    """Fetch options chain for the nearest 3 expirations."""
    t = yf.Ticker(ticker)
    try:
        expirations = t.options[:3]
    except Exception:
        return {"calls": [], "puts": [], "expirations": [], "error": "No options data"}

    all_calls = []
    all_puts = []

    try:
        spot = float(t.fast_info.last_price)
    except Exception:
        spot = 450.0

    for exp in expirations:
        try:
            chain = t.option_chain(exp)
        except Exception:
            continue
        for side, df in [("call", chain.calls), ("put", chain.puts)]:
            df = df.copy()
            df["expiration"] = exp
            df["side"] = side
            for col in ["volume", "openInterest"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            if "lastPrice" not in df.columns:
                continue
            df["lastPrice"] = pd.to_numeric(df["lastPrice"], errors="coerce").fillna(0)
            df["estimated_premium"] = df["lastPrice"] * 100 * df.get("volume", 0)
            df["volume_oi_ratio"] = df.get("volume", 0) / (df.get("openInterest", 0) + 1)
            df["unusual_flag"] = (df.get("volume", 0) > 2 * df.get("openInterest", 1)) | (df["estimated_premium"] > 500_000)

            if "gamma" in df.columns and "openInterest" in df.columns:
                df["gamma"] = pd.to_numeric(df["gamma"], errors="coerce").fillna(0)
                df["gex"] = df["gamma"] * df["openInterest"] * 100 * spot
            else:
                df["gex"] = 0

            rows = []
            for _, r in df.iterrows():
                rows.append({
                    "expiration": exp,
                    "strike": _clean(float(r.get("strike", 0))),
                    "side": side,
                    "lastPrice": _clean(float(r.get("lastPrice", 0))),
                    "bid": _clean(float(r.get("bid", 0))),
                    "ask": _clean(float(r.get("ask", 0))),
                    "volume": int(r.get("volume", 0) or 0),
                    "openInterest": int(r.get("openInterest", 0) or 0),
                    "impliedVolatility": _clean(float(r.get("impliedVolatility", 0) or 0)),
                    "delta": _clean(float(r.get("delta", 0) or 0)) if "delta" in r else None,
                    "gamma": _clean(float(r.get("gamma", 0) or 0)) if "gamma" in r else None,
                    "theta": _clean(float(r.get("theta", 0) or 0)) if "theta" in r else None,
                    "estimated_premium": _clean(float(r.get("estimated_premium", 0))),
                    "volume_oi_ratio": _clean(float(r.get("volume_oi_ratio", 0))),
                    "unusual_flag": bool(r.get("unusual_flag", False)),
                    "gex": _clean(float(r.get("gex", 0))),
                })
            if side == "call":
                all_calls.extend(rows)
            else:
                all_puts.extend(rows)

    return {"calls": all_calls, "puts": all_puts, "expirations": list(expirations)}


def get_leadership_quotes() -> list:
    results = []
    for sym in LEADERSHIP:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            price = _clean(float(info.last_price))
            prev = _clean(float(info.previous_close))
            chg = round(price - prev, 2) if price and prev else None
            chg_pct = round((price - prev) / prev * 100, 2) if price and prev and prev != 0 else None
            results.append({
                "symbol": sym,
                "price": price,
                "change": chg,
                "change_pct": chg_pct,
                "nasdaq_weight": NASDAQ_WEIGHTS.get(sym, 0.01),
                "bullish": chg_pct is not None and chg_pct > 0,
            })
        except Exception:
            results.append({"symbol": sym, "price": None, "change": None, "change_pct": None,
                            "nasdaq_weight": NASDAQ_WEIGHTS.get(sym, 0.01), "bullish": None})
    return results


def get_news(ticker: str = "QQQ") -> list:
    SENTIMENT_KEYWORDS = {
        "bullish": ["surge", "rally", "gain", "rise", "beat", "record", "high", "upgrade", "buy", "positive", "strong", "bullish"],
        "bearish": ["drop", "fall", "decline", "loss", "miss", "low", "downgrade", "sell", "negative", "crash", "recession", "weak", "bearish", "slump"],
    }
    # Pull news from multiple relevant tickers and merge
    tickers_to_fetch = ["QQQ", "NVDA", "MSFT", "SPY"] if ticker in ("QQQ", "SPY") else [ticker]
    seen, results = set(), []

    for tick in tickers_to_fetch:
        try:
            raw = yf.Ticker(tick).news or []
            for item in raw[:12]:
                # yfinance v0.2.50+ nests everything under 'content'
                content = item.get("content") or item
                title = content.get("title") or item.get("title", "")
                if not title or title in seen:
                    continue
                seen.add(title)

                # Link: prefer canonicalUrl, fall back to clickThroughUrl / link
                link = (
                    (content.get("canonicalUrl") or {}).get("url")
                    or (content.get("clickThroughUrl") or {}).get("url")
                    or item.get("link", "")
                )
                # Publisher
                publisher = (
                    (content.get("provider") or {}).get("displayName")
                    or item.get("publisher", "")
                )
                # Timestamp: ISO string from new API or Unix int from old API
                ts_raw = content.get("pubDate") or content.get("displayTime")
                if ts_raw:
                    timestamp = ts_raw
                else:
                    pub_time = item.get("providerPublishTime", 0)
                    timestamp = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat() if pub_time else None

                # Sentiment scoring
                title_lower = title.lower()
                bull = sum(1 for w in SENTIMENT_KEYWORDS["bullish"] if w in title_lower)
                bear = sum(1 for w in SENTIMENT_KEYWORDS["bearish"] if w in title_lower)
                sentiment = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"

                results.append({
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "timestamp": timestamp,
                    "sentiment": sentiment,
                    "summary": content.get("summary", ""),
                    "ticker": tick,
                })
        except Exception:
            continue

    # Sort newest first, cap at 25
    results.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return results[:25]


FUTURES_MAP = [
    {"symbol": "NQ=F", "instrument": "MNQ", "name": "Micro NQ", "dollars_per_point": 2.0},
    {"symbol": "ES=F", "instrument": "MES", "name": "Micro ES", "dollars_per_point": 5.0},
    {"symbol": "GC=F", "instrument": "MGC", "name": "Micro Gold", "dollars_per_point": 10.0},
]


def get_futures_quotes() -> list:
    """Fetch live NQ=F, ES=F, GC=F prices."""
    results = []
    for spec in FUTURES_MAP:
        sym = spec["symbol"]
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            price = _clean(float(info.last_price))
            prev = _clean(float(info.previous_close))
            chg = round(price - prev, 2) if price and prev else None
            chg_pct = round((price - prev) / prev * 100, 2) if price and prev and prev != 0 else None
            results.append({**spec, "price": price, "prev_close": prev, "change": chg, "change_pct": chg_pct, "bullish": chg_pct is not None and chg_pct > 0})
        except Exception:
            results.append({**spec, "price": None, "prev_close": None, "change": None, "change_pct": None, "bullish": None})
    return results


def get_daily_bars(ticker: str = "QQQ", period: str = "3mo") -> list:
    """Fetch daily OHLCV bars for HTF analysis."""
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return []
        df = df.reset_index()
        bars = []
        for _, row in df.iterrows():
            dt = row.get("Date") or row.get("Datetime")
            bars.append({
                "time": str(dt.date()) if hasattr(dt, "date") else str(dt),
                "open":  _clean(float(row["Open"].iloc[0]  if hasattr(row["Open"],  "iloc") else row["Open"])),
                "high":  _clean(float(row["High"].iloc[0]  if hasattr(row["High"],  "iloc") else row["High"])),
                "low":   _clean(float(row["Low"].iloc[0]   if hasattr(row["Low"],   "iloc") else row["Low"])),
                "close": _clean(float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])),
                "volume":_clean(float(row["Volume"].iloc[0]if hasattr(row["Volume"],"iloc") else row["Volume"])),
            })
        return bars
    except Exception:
        return []


def get_tech9() -> dict:
    """Fetch Tech-9 breadth: Dakota's 9 key NASDAQ stocks for bias confirmation."""
    result = []
    for ticker, name in TECH9_TICKERS:
        try:
            info = yf.Ticker(ticker).fast_info
            price = _clean(float(info.last_price))
            prev_close = _clean(float(info.previous_close))
            change_pct = (
                round((price - prev_close) / prev_close * 100, 2)
                if price and prev_close and prev_close != 0
                else None
            )
        except Exception:
            change_pct = None
        result.append({
            "ticker": ticker,
            "name": name,
            "change_pct": change_pct,
            "bullish": (change_pct or 0) > 0,
        })
    green_count = sum(1 for s in result if s["bullish"])
    return {
        "stocks": result,
        "green_count": green_count,
        "red_count": len(result) - green_count,
    }


def get_chart_bars(symbol: str, interval: str = "5m", period: str = "1d") -> list:
    """Return OHLCV bars for charting. Handles multi-level column names from yfinance."""
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return []
        df = df.reset_index()
        # yfinance sometimes returns MultiIndex columns — flatten them
        if hasattr(df.columns, 'levels'):
            df.columns = [c[0] if c[1] == '' or c[1] == symbol else c[0] for c in df.columns]
        ts_col = "Datetime" if "Datetime" in df.columns else "Date"
        bars = []
        for _, row in df.iterrows():
            ts = row[ts_col]
            try:
                o = _clean(float(row["Open"]))
                h = _clean(float(row["High"]))
                l = _clean(float(row["Low"]))
                c = _clean(float(row["Close"]))
                v = _clean(float(row["Volume"]))
            except Exception:
                continue
            if None in (o, h, l, c):
                continue
            bars.append({
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": o, "high": h, "low": l, "close": c, "volume": v or 0,
            })
        return bars
    except Exception:
        return []
