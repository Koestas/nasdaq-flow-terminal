from fastapi import APIRouter
import yfinance as yf
from providers.schwab import status as schwab_status
from database import DB_PATH
import os

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/status")
async def provider_status():
    # Yahoo Finance check
    yahoo_ok = False
    yahoo_msg = ""
    try:
        t = yf.Ticker("QQQ")
        price = t.fast_info.last_price
        yahoo_ok = price is not None and price > 0
        yahoo_msg = f"QQQ: ${price:.2f}" if yahoo_ok else "No price returned"
    except Exception as e:
        yahoo_msg = str(e)

    # SQLite check
    db_ok = os.path.exists(DB_PATH) or True  # will be created on first write
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    schwab = schwab_status()

    return {
        "providers": {
            "yahoo": {
                "status": "ok" if yahoo_ok else "error",
                "message": yahoo_msg,
                "features": ["quotes", "options_chain", "news", "intraday"],
            },
            "schwab": schwab,
            "sqlite": {
                "status": "ok" if db_ok else "error",
                "path": DB_PATH,
                "size_bytes": db_size,
            },
        }
    }
