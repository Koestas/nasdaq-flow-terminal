from fastapi import APIRouter, HTTPException
from database import get_snapshots, get_snapshot_by_id, save_snapshot
from routes.market import market_overview

router = APIRouter(prefix="/api/replay", tags=["replay"])


@router.get("/snapshots")
async def list_snapshots(limit: int = 50):
    try:
        return {"snapshots": await get_snapshots(limit)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: int):
    snap = await get_snapshot_by_id(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.post("/save")
async def save_current_snapshot():
    """Save current market state as a snapshot."""
    try:
        data = await market_overview()
        ts = await save_snapshot(data)
        return {"saved": True, "timestamp": ts}
    except Exception as e:
        return {"error": str(e)}


@router.get("/compare")
async def compare_snapshots(id1: int, id2: int):
    s1 = await get_snapshot_by_id(id1)
    s2 = await get_snapshot_by_id(id2)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")

    d1 = s1.get("data", {})
    d2 = s2.get("data", {})

    def _get_nested(d, *keys):
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return None
        return d

    comparison = {
        "snapshot_1": {"id": id1, "timestamp": s1["timestamp"]},
        "snapshot_2": {"id": id2, "timestamp": s2["timestamp"]},
        "metrics": {
            "qqq_price": {
                "t1": _get_nested(d1, "price", "price"),
                "t2": _get_nested(d2, "price", "price"),
            },
            "vwap_status": {
                "t1": d1.get("vwap_status"),
                "t2": d2.get("vwap_status"),
            },
            "bias_score": {
                "t1": _get_nested(d1, "bias", "score"),
                "t2": _get_nested(d2, "bias", "score"),
            },
            "bias_label": {
                "t1": _get_nested(d1, "bias", "label"),
                "t2": _get_nested(d2, "bias", "label"),
            },
            "net_wave": {
                "t1": _get_nested(d1, "wave_summary", "net_wave"),
                "t2": _get_nested(d2, "wave_summary", "net_wave"),
            },
            "leadership_green": {
                "t1": _get_nested(d1, "leadership_summary", "green"),
                "t2": _get_nested(d2, "leadership_summary", "green"),
            },
        },
    }
    return comparison
