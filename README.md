# Micro Futures Analyzer (MFA)

A free, open-source trading terminal for micro futures (MNQ, MES, MGC) built on ICT/SMC concepts. Real-time signals, backtesting, risk management, and an ICT coaching replay mode — all running locally on free data.

![MFA Terminal](https://img.shields.io/badge/stack-FastAPI%20%2B%20React-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Data](https://img.shields.io/badge/data-Yahoo%20Finance%20(free)-yellow)

---

## What it does

**Signal Terminal** — 19 live pages covering everything a micro futures day trader needs:

- **ICT Signals** — FVG/iFVG detection (with displacement), order blocks, liquidity sweeps, MSS/CHoCH confirmation, OTE zone (0.618–0.786), session levels (Asia/London/NY), draw on liquidity, PO3/AMD phase
- **NY Killzone Strategy** — HTF-aligned ICT setup scoring (0–100 pts), grade A/A+ filter, 3-day volatility regime gate, partial TP at 1R→BE, tested at 60–75% win rate
- **Backtest Engine** — 5m precision (90 days) or 1h extended (720 days, Yahoo Finance max). Monthly breakdown, equity curve, per-trade detail
- **Risk Manager** — trailing floor tracker, position sizer (MNQ/MES/MGC), daily trade plan, profit target tracker
- **ICT Learning Mode** — pick any past date, step forward bar by bar, AI coach panel explains what's happening live
- **Charts** — lightweight-charts with ICT overlays: FVG, iFVG, OB, EQL/EQH, DOL, OR 30m, Pivot Points, Big Figure levels, 200 SMA, VWAP
- **Live News Ticker** — scrolling Bloomberg-style bar with sentiment-coded headlines + market alerts
- **Pre-Trade Checklist** — ICT criteria checklist with live backend data

---

## Backtest results (free Yahoo Finance data, 5m bars)

| Instrument | Period | Trades | Win Rate | Profit Factor | Monthly @3ct |
|-----------|--------|--------|----------|--------------|-------------|
| MNQ | 45-day validated | 12 | **75%** | 3.8 | **$2,252** |
| MNQ | 720-day (1h) | 60 | 68.3% | 3.46 | $564 |
| MES | 180-day (1h) | 21 | 61.9% | 1.36 | ~$326 |

*Tariff crash period (Apr–May 2026) suppressed trade frequency by design — the 3-day vol regime filter correctly blocked trading during exceptional volatility.*

---

## Stack

```
backend/    FastAPI (Python 3.12) + SQLite
frontend/   React 18 + Vite + Tailwind CSS
data/       Yahoo Finance (free, ~15min delay) — no subscription required
```

---

## Quick start

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Frontend
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

No API keys required. Yahoo Finance data works out of the box.

**Optional:** Schwab API integration is pre-wired (OAuth flow in `/api/schwab`) for live data when you have a brokerage account.

---

## Pages

| Page | What it shows |
|------|--------------|
| Overview | Bias score, VWAP, regime, macro, killzone status |
| ICT | Full ICT signal panel — sweeps, FVGs, OBs, DOL, scoring |
| Charts | Candlestick + all ICT overlays, VWAP, 200 SMA |
| Backtest | NY Killzone strategy backtest + Test Lab (experimental flags) |
| Risk | Risk manager — trailing floor, position sizing, daily P&L |
| Learn | Step-forward replay with ICT coaching panel |
| Checklist | Pre-trade criteria checklist |
| Wave / GEX | Options flow and gamma exposure |
| Leadership | Market breadth, sector rotation |
| Tape | Time & sales replay |
| Journal | Trade journal with P&L tracking |

---

## ICT Signal Engine

Built on ICT 2022/2023 concepts:

- **FVG / iFVG** — fair value gap detection with displacement filter; inverted FVGs flagged as entry zones
- **Liquidity sweeps** — FRESH (≤90 min) vs STALE classification, tracks which session level was swept
- **MSS / CHoCH** — market structure shift and change of character confirmation
- **OTE Zone** — 0.618–0.786 Fibonacci optimal trade entry
- **IPDA levels** — 20/40/60 day institutional delivery ranges
- **SMT divergence** — NQ/ES correlation break detection (5m resolution)
- **PO3 / AMD** — accumulation/manipulation/distribution phase detection
- **Session levels** — Asia high/low, London high/low, prev day H/L/C, today H/L

Scoring system (100 pts):

| Factor | Points |
|--------|--------|
| NY Killzone timing | 20 |
| HTF trend aligned | 15 |
| iFVG at entry | 15 |
| Displacement | 10 |
| Draw on liquidity | 20 |
| Discount/Premium zone | 10 |
| Order Block confluence | 5 |
| VWAP position | 5 |

Day quality multiplier: Mon 0.80 / Tue–Wed 1.0 / Thu 0.90 / Fri 0.75

---

## Data sources

- **Yahoo Finance** — OHLCV bars (free, ~15 min delayed). Supported intervals: 1m, 5m, 15m, 30m, 1h, 1d. Max history: 90 days at 5m, 720 days at 1h.
- **ForexFactory** — Economic calendar, USD high-impact events (4hr TTL cache)
- **Schwab API** — Pre-wired for live data (requires brokerage account + OAuth setup)

---

## License

MIT — free to use, modify, and sell. Attribution appreciated but not required.

---

## Support

If this saved you time or money, consider supporting development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?logo=ko-fi)](https://ko-fi.com)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsor-ea4aaa?logo=github)](https://github.com/sponsors)

---

*Not financial advice. Past backtest results do not guarantee future performance.*
