from fastapi import APIRouter, Query
from providers.yahoo import get_options_chain, get_qqq_price
from engines.stats import calc_wave, calc_gex, calc_top_flow, calc_unusual, calc_heatmap
from database import get_wave_history, save_wave_point

router = APIRouter(prefix="/api/flow", tags=["flow"])


def _get_chain_and_price():
    price_data = get_qqq_price()
    chain = get_options_chain("QQQ")
    calls = chain.get("calls", [])
    puts = chain.get("puts", [])
    price = price_data.get("price") or 450.0
    return calls, puts, price, chain.get("expirations", [])


@router.get("/wave")
async def flow_wave():
    try:
        calls, puts, price, _ = _get_chain_and_price()
        wave = calc_wave(calls, puts)
        await save_wave_point(
            call_wave=wave.get("call_wave") or 0,
            put_wave=wave.get("put_wave") or 0,
            net_wave=wave.get("net_wave") or 0,
            qqq_price=price,
        )
        history = await get_wave_history(60)
        return {**wave, "history": history, "qqq_price": price}
    except Exception as e:
        return {"error": str(e)}


@router.get("/gex")
async def flow_gex():
    try:
        calls, puts, price, _ = _get_chain_and_price()
        return calc_gex(calls, puts, price)
    except Exception as e:
        return {"error": str(e)}


@router.get("/top")
async def flow_top(limit: int = Query(20, ge=1, le=50)):
    try:
        calls, puts, _, _ = _get_chain_and_price()
        return {"contracts": calc_top_flow(calls, puts, top_n=limit)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/unusual")
async def flow_unusual():
    try:
        calls, puts, _, _ = _get_chain_and_price()
        return {"contracts": calc_unusual(calls, puts)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/raw-chain")
async def flow_raw_chain(
    expiration: str = Query(None),
    side: str = Query(None, regex="^(call|put)$"),
    min_volume: int = Query(0),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
):
    try:
        calls, puts, _, expirations = _get_chain_and_price()
        all_contracts = calls + puts
        if expiration:
            all_contracts = [c for c in all_contracts if c.get("expiration") == expiration]
        if side:
            all_contracts = [c for c in all_contracts if c.get("side") == side]
        if min_volume > 0:
            all_contracts = [c for c in all_contracts if (c.get("volume") or 0) >= min_volume]
        all_contracts.sort(key=lambda c: c.get("volume") or 0, reverse=True)
        total = len(all_contracts)
        start = (page - 1) * per_page
        end = start + per_page
        return {
            "contracts": all_contracts[start:end],
            "total": total,
            "page": page,
            "per_page": per_page,
            "expirations": expirations,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/heatmap")
async def flow_heatmap():
    try:
        calls, puts, _, _ = _get_chain_and_price()
        return calc_heatmap(calls, puts)
    except Exception as e:
        return {"error": str(e)}
