from fastapi import APIRouter
from providers.yahoo import get_options_chain, get_qqq_price
from engines.stats import calc_top_flow, _premium_size
from database import get_snapshots

router = APIRouter(prefix="/api/tape", tags=["tape"])


@router.get("/live")
async def tape_live():
    """Returns recent tape (top flow contracts formatted as tape entries)."""
    try:
        price_data = get_qqq_price()
        chain = get_options_chain("QQQ")
        calls = chain.get("calls", [])
        puts = chain.get("puts", [])
        price = price_data.get("price") or 450.0

        tape = []
        for c in calls + puts:
            vol = c.get("volume") or 0
            prem = c.get("estimated_premium") or 0
            if vol < 10 or prem < 5000:
                continue
            tape.append({
                "ticker": "QQQ",
                "expiration": c.get("expiration"),
                "strike": c.get("strike"),
                "side": c.get("side"),
                "price": c.get("lastPrice"),
                "volume": vol,
                "open_interest": c.get("openInterest"),
                "premium": prem,
                "side_estimate": "ask-side" if vol > (c.get("openInterest") or 0) * 0.5 else "bid-side",
                "signal": "bullish" if c.get("side") == "call" else "bearish",
                "premium_size": _premium_size(prem),
                "unusual": c.get("unusual_flag", False),
            })
        tape.sort(key=lambda x: x["premium"], reverse=True)
        return {"tape": tape[:100], "qqq_price": price}
    except Exception as e:
        return {"error": str(e)}


@router.get("/saved")
async def tape_saved(limit: int = 50):
    try:
        snaps = await get_snapshots(limit)
        return {"snapshots": snaps}
    except Exception as e:
        return {"error": str(e)}
