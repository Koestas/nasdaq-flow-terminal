"""Risk management API routes — prop firm math + position sizing."""
from fastapi import APIRouter, Query
from engines.risk import calc_account_status, size_position, daily_trade_plan, INSTRUMENTS

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/account")
async def account_status(
    balance: float = Query(25000.0, description="Current account balance"),
    highest: float = Query(None, description="Session highest balance (defaults to balance)"),
):
    status = calc_account_status(balance, highest)
    plan = daily_trade_plan(status)
    return {**status, "trade_plan": plan}


@router.get("/size")
async def position_size(
    instrument: str = Query("MNQ", description="MNQ, MES, or MGC"),
    stop_points: float = Query(..., description="Stop distance in points"),
    balance: float = Query(25000.0),
    highest: float = Query(None),
    risk_pct: float = Query(0.3, description="Fraction of daily risk remaining to use per trade"),
    max_risk: float = Query(300.0, description="Absolute max risk per trade in dollars"),
):
    status = calc_account_status(balance, highest)
    sizing = size_position(
        instrument=instrument,
        stop_points=stop_points,
        account_status=status,
        risk_per_trade_pct=risk_pct,
        max_risk_per_trade=max_risk,
    )
    return {
        "account": {
            "balance": status["current_balance"],
            "daily_risk_remaining": status["daily_risk_remaining"],
            "status": status["status"],
        },
        "sizing": sizing,
    }


@router.get("/instruments")
async def instruments():
    return {
        k: {
            **v,
            "example_stop_5pt_risk": round(5 * v["dollars_per_point"], 2),
            "example_stop_10pt_risk": round(10 * v["dollars_per_point"], 2),
        }
        for k, v in INSTRUMENTS.items()
    }


@router.get("/payout")
async def payout_status(
    balance: float = Query(25000.0),
    highest: float = Query(None),
):
    status = calc_account_status(balance, highest)
    return {
        "current_balance": status["current_balance"],
        "payout_ready": status["payout_ready"],
        "payout_threshold": status["payout_threshold"],
        "to_threshold": status["to_payout_threshold"],
        "max_payout": status["max_payout"],
        "safe_trigger": status["safe_payout_trigger"],
        "to_safe_trigger": status["to_safe_trigger"],
        "safe_after_payout": status["safe_after_payout"],
        "days_at_300": status["days_at_300"],
        "days_at_400": status["days_at_400"],
        "days_at_500": status["days_at_500"],
        "message": (
            "Ready to take $1,500 payout!" if status["payout_ready"] and status["current_balance"] >= status["safe_payout_trigger"]
            else f"Need ${status['to_safe_trigger']:.0f} more for safe payout trigger"
            if not status["payout_ready"] else
            f"Above threshold — need ${status['to_safe_trigger']:.0f} more for safe payout buffer"
        ),
    }
