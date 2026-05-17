"""Schwab OAuth2 + market data routes."""
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse, JSONResponse
import providers.schwab as schwab

router = APIRouter(prefix="/api/schwab", tags=["schwab"])


@router.get("/login")
async def login():
    if not schwab.is_configured():
        return JSONResponse(
            status_code=400,
            content={"error": "Schwab not configured. Set SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_CALLBACK_URL in .env"}
        )
    return RedirectResponse(schwab.get_auth_url())


@router.get("/callback")
async def callback(code: str = Query(...)):
    try:
        await schwab.exchange_code(code)
        return RedirectResponse("/?schwab=connected")
    except Exception as e:
        return RedirectResponse(f"/?schwab=error&msg={str(e)[:100]}")


@router.get("/status")
async def status():
    return schwab.status()


@router.get("/quote/{symbol}")
async def quote(symbol: str):
    data = await schwab.get_quote(symbol.upper())
    if data is None:
        return JSONResponse(status_code=503, content={"error": "Schwab unavailable or not authenticated"})
    return data


@router.get("/quotes")
async def quotes(symbols: str = Query(...)):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    data = await schwab.get_quotes(syms)
    if not data:
        return JSONResponse(status_code=503, content={"error": "Schwab unavailable or not authenticated"})
    return data


@router.get("/options/{symbol}")
async def options_chain(symbol: str, strike_count: int = Query(40)):
    data = await schwab.get_options_chain(symbol.upper(), strike_count)
    if data is None:
        return JSONResponse(status_code=503, content={"error": "Schwab unavailable or not authenticated"})
    return data


@router.get("/history/{symbol}")
async def price_history(
    symbol: str,
    period_type: str = Query("day"),
    period: int = Query(2),
    frequency_type: str = Query("minute"),
    frequency: int = Query(1),
    extended_hours: bool = Query(True),
):
    data = await schwab.get_price_history(
        symbol.upper(), period_type, period, frequency_type, frequency, extended_hours
    )
    if data is None:
        return JSONResponse(status_code=503, content={"error": "Schwab unavailable or not authenticated"})
    return data


@router.get("/vix")
async def vix():
    val = await schwab.get_vix()
    return {"vix": val, "source": "schwab"}
