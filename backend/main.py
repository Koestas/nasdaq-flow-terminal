from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncio
import uvicorn

load_dotenv()

from database import init_db
from routes.market import router as market_router
from routes.flow import router as flow_router
from routes.tape import router as tape_router
from routes.replay import router as replay_router
from routes.journal import router as journal_router
from routes.providers import router as providers_router
from routes.schwab import router as schwab_router
from routes.ict import router as ict_router
from routes.risk import router as risk_router
from routes.learn import router as learn_router
from routes.backtest import router as backtest_router


async def _background_refresh():
    """Proactively warm the data cache every 5 minutes.
    Runs regardless of whether any browser tab is open."""
    import providers.yahoo as yf
    from providers.calendar import get_calendar

    await asyncio.sleep(15)  # let server fully start first
    while True:
        try:
            yf.get_qqq_price()
            yf.get_futures_quotes()
            yf.get_news()
            yf.get_intraday("QQQ", "5m")
            get_calendar()
        except Exception:
            pass
        await asyncio.sleep(300)  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(_background_refresh())
    yield
    task.cancel()


app = FastAPI(title="Micro Futures Analyzer", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(flow_router)
app.include_router(tape_router)
app.include_router(replay_router)
app.include_router(journal_router)
app.include_router(providers_router)
app.include_router(schwab_router)
app.include_router(ict_router)
app.include_router(risk_router)
app.include_router(learn_router)
app.include_router(backtest_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc), "path": str(request.url)})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
