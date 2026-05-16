"""Charles Schwab API stub — wire up when credentials are configured.

Schwab Developer API docs: https://developer.schwab.com/
Free for account holders. Requires OAuth2 flow.
"""
import os
from typing import Optional


SCHWAB_APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
SCHWAB_APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")


def is_configured() -> bool:
    return bool(SCHWAB_APP_KEY and SCHWAB_APP_SECRET)


async def get_quote(symbol: str) -> Optional[dict]:
    """GET /marketdata/v1/quotes/{symbol}"""
    if not is_configured():
        return None
    # TODO: implement OAuth2 token refresh + quote fetch
    raise NotImplementedError("Schwab integration not yet implemented")


async def get_options_chain(symbol: str = "QQQ") -> Optional[dict]:
    """GET /marketdata/v1/chains"""
    if not is_configured():
        return None
    raise NotImplementedError("Schwab integration not yet implemented")


def status() -> dict:
    return {
        "provider": "schwab",
        "configured": is_configured(),
        "status": "ready" if is_configured() else "not_configured",
        "message": "Schwab API key loaded" if is_configured() else "Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env",
    }
