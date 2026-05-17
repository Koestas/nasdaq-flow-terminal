"""Charles Schwab Developer API — OAuth2 + Market Data"""
import os, time, base64, json, httpx
from typing import Optional
from urllib.parse import urlencode

SCHWAB_BASE = "https://api.schwabapi.com"
AUTH_URL = f"{SCHWAB_BASE}/v1/oauth/authorize"
TOKEN_URL = f"{SCHWAB_BASE}/v1/oauth/token"

APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "")

TOKENS_FILE = os.path.join(os.path.dirname(__file__), "..", ".schwab_tokens.json")
_tokens: dict = {}


def _load_tokens():
    global _tokens
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE) as f:
                _tokens = json.load(f)
    except Exception:
        _tokens = {}


def _save_tokens(t: dict):
    global _tokens
    _tokens = t
    try:
        with open(TOKENS_FILE, "w") as f:
            json.dump(t, f, indent=2)
    except Exception:
        pass


def is_configured() -> bool:
    return bool(APP_KEY and APP_SECRET and CALLBACK_URL)


def has_tokens() -> bool:
    if not _tokens:
        _load_tokens()
    return bool(_tokens.get("access_token"))


def get_auth_url() -> str:
    params = {"response_type": "code", "client_id": APP_KEY, "redirect_uri": CALLBACK_URL}
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    creds = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK_URL},
            timeout=15,
        )
        resp.raise_for_status()
        t = resp.json()
        t["expires_at"] = time.time() + t.get("expires_in", 1800)
        _save_tokens(t)
        return t


async def _refresh() -> bool:
    _load_tokens()
    if not _tokens.get("refresh_token"):
        return False
    creds = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": _tokens["refresh_token"]},
            timeout=15,
        )
        if resp.status_code == 200:
            t = resp.json()
            t["expires_at"] = time.time() + t.get("expires_in", 1800)
            t.setdefault("refresh_token", _tokens["refresh_token"])
            _save_tokens(t)
            return True
        return False


async def _headers() -> Optional[dict]:
    _load_tokens()
    if not _tokens.get("access_token"):
        return None
    if _tokens.get("expires_at", 0) - time.time() < 300:
        ok = await _refresh()
        if not ok:
            return None
    return {"Authorization": f"Bearer {_tokens['access_token']}"}


async def get_quote(symbol: str) -> Optional[dict]:
    h = await _headers()
    if not h:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SCHWAB_BASE}/marketdata/v1/quotes",
                             headers=h, params={"symbols": symbol, "fields": "quote,reference"}, timeout=10)
        if r.status_code == 200:
            return r.json().get(symbol, {})
    return None


async def get_quotes(symbols: list) -> dict:
    h = await _headers()
    if not h:
        return {}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SCHWAB_BASE}/marketdata/v1/quotes",
                             headers=h, params={"symbols": ",".join(symbols), "fields": "quote"}, timeout=10)
        if r.status_code == 200:
            return r.json()
    return {}


async def get_options_chain(symbol: str = "QQQ", strike_count: int = 40) -> Optional[dict]:
    h = await _headers()
    if not h:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SCHWAB_BASE}/marketdata/v1/chains", headers=h,
                             params={"symbol": symbol, "contractType": "ALL",
                                     "strikeCount": strike_count, "includeUnderlyingQuote": True,
                                     "strategy": "SINGLE"}, timeout=15)
        if r.status_code == 200:
            return r.json()
    return None


async def get_price_history(symbol: str = "QQQ", period_type: str = "day", period: int = 2,
                            frequency_type: str = "minute", frequency: int = 1,
                            extended_hours: bool = True) -> Optional[dict]:
    h = await _headers()
    if not h:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SCHWAB_BASE}/marketdata/v1/pricehistory", headers=h,
                             params={"symbol": symbol, "periodType": period_type, "period": period,
                                     "frequencyType": frequency_type, "frequency": frequency,
                                     "needExtendedHoursData": extended_hours}, timeout=15)
        if r.status_code == 200:
            return r.json()
    return None


async def get_vix() -> Optional[float]:
    h = await _headers()
    if not h:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SCHWAB_BASE}/marketdata/v1/quotes",
                             headers=h, params={"symbols": "$VIX.X", "fields": "quote"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("$VIX.X", {}).get("quote", {}).get("lastPrice")
    return None


def status() -> dict:
    _load_tokens()
    configured = is_configured()
    authed = has_tokens() if configured else False
    remaining = None
    if _tokens.get("expires_at"):
        secs = int(_tokens["expires_at"] - time.time())
        remaining = f"{secs // 60}m {secs % 60}s" if secs > 0 else "expired"
    return {
        "provider": "schwab", "configured": configured, "authenticated": authed,
        "token_expires": remaining,
        "status": "ok" if authed else ("ready" if configured else "not_configured"),
        "message": ("Live data active" if authed
                    else "Credentials loaded — visit /api/schwab/login to authenticate" if configured
                    else "Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env"),
        "auth_url": get_auth_url() if configured and not authed else None,
    }
