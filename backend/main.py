from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

load_dotenv()

from database import init_db
from routes.market import router as market_router
from routes.flow import router as flow_router
from routes.tape import router as tape_router
from routes.replay import router as replay_router
from routes.journal import router as journal_router
from routes.providers import router as providers_router

app = FastAPI(title="NASDAQ Flow Terminal", version="1.0.0")

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


@app.on_event("startup")
async def startup():
    await init_db()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc), "path": str(request.url)})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
