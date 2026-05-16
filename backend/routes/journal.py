from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import save_trade, get_trades

router = APIRouter(prefix="/api/journal", tags=["journal"])


class TradeEntry(BaseModel):
    symbol: str = "MNQ"
    direction: Optional[str] = None  # "long" | "short"
    entry: Optional[float] = None
    exit: Optional[float] = None
    result: Optional[float] = None
    r_multiple: Optional[float] = None
    setup_type: Optional[str] = None
    bias_at_entry: Optional[str] = None
    confidence: Optional[int] = None
    notes: Optional[str] = None
    mistake_tag: Optional[str] = None
    lesson: Optional[str] = None


@router.get("/trades")
async def list_trades(limit: int = 100):
    try:
        return {"trades": await get_trades(limit)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/trades")
async def add_trade(trade: TradeEntry):
    try:
        await save_trade(trade.dict())
        return {"saved": True}
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def journal_stats():
    try:
        trades = await get_trades(500)
        if not trades:
            return {"total": 0}

        total = len(trades)
        wins = [t for t in trades if (t.get("result") or 0) > 0]
        losses = [t for t in trades if (t.get("result") or 0) < 0]
        r_values = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]
        win_rate = round(len(wins) / total * 100, 1) if total else 0
        avg_r = round(sum(r_values) / len(r_values), 2) if r_values else None
        total_result = round(sum(t.get("result") or 0 for t in trades), 2)

        by_setup: dict = {}
        for t in trades:
            s = t.get("setup_type") or "untagged"
            by_setup.setdefault(s, {"count": 0, "wins": 0, "total_r": 0})
            by_setup[s]["count"] += 1
            if (t.get("result") or 0) > 0:
                by_setup[s]["wins"] += 1
            by_setup[s]["total_r"] += t.get("r_multiple") or 0

        mistake_counts: dict = {}
        for t in trades:
            m = t.get("mistake_tag")
            if m:
                mistake_counts[m] = mistake_counts.get(m, 0) + 1

        return {
            "total": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_r": avg_r,
            "total_result": total_result,
            "by_setup": by_setup,
            "top_mistakes": sorted(mistake_counts.items(), key=lambda x: -x[1])[:5],
        }
    except Exception as e:
        return {"error": str(e)}
