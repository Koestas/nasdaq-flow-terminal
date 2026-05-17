"""Prop firm risk engine — Lucid 25k Pro rules + position sizing."""
from typing import Optional

# Instrument specs: dollars per point
INSTRUMENTS = {
    "MNQ": {"name": "Micro NQ", "dollars_per_point": 2.0, "proxy": "QQQ", "session": "NY"},
    "MES": {"name": "Micro ES", "dollars_per_point": 5.0, "proxy": "SPY", "session": "NY"},
    "MGC": {"name": "Micro Gold", "dollars_per_point": 10.0, "proxy": "GC=F", "session": "Asia"},
}

# Lucid 25k Pro constants
STARTING_BALANCE = 25_000.0
DAILY_LOSS_LIMIT = 1_000.0
TRAIL_FLOOR_STOPS_AT = 25_100.0   # floor stops trailing once it reaches this
PAYOUT_THRESHOLD = 26_100.0       # minimum balance to request payout
MAX_PAYOUT = 1_500.0
SAFE_AFTER_PAYOUT = 26_500.0      # balance must stay above this after payout
SAFE_PAYOUT_TRIGGER = SAFE_AFTER_PAYOUT + MAX_PAYOUT  # 28,000


def calc_trailing_floor(prev_close_balance: float) -> float:
    """EOD trailing max-loss floor. Trails yesterday's close, locks at TRAIL_FLOOR_STOPS_AT."""
    floor = prev_close_balance - DAILY_LOSS_LIMIT
    return min(floor, TRAIL_FLOOR_STOPS_AT)


def calc_account_status(current_balance: float, prev_close_balance: Optional[float] = None) -> dict:
    """
    Full account status for the risk manager.

    Args:
        current_balance: Current P&L-adjusted balance
        prev_close_balance: Yesterday's EOD closing balance (EOD trailing drawdown baseline)
    """
    if prev_close_balance is None:
        prev_close_balance = current_balance

    floor = calc_trailing_floor(prev_close_balance)
    daily_risk_remaining = current_balance - floor
    daily_pnl = current_balance - STARTING_BALANCE

    # How far from payout target
    to_payout = max(0.0, PAYOUT_THRESHOLD - current_balance)
    to_safe_trigger = max(0.0, SAFE_PAYOUT_TRIGGER - current_balance)
    payout_ready = current_balance >= PAYOUT_THRESHOLD

    # Days to build buffer at various daily targets
    def days_needed(target_per_day: float) -> Optional[int]:
        if target_per_day <= 0 or current_balance >= SAFE_PAYOUT_TRIGGER:
            return 0
        needed = SAFE_PAYOUT_TRIGGER - current_balance
        return max(1, round(needed / target_per_day))

    # Status label
    if current_balance <= floor:
        status = "BLOWN"
        status_color = "red"
    elif daily_risk_remaining < DAILY_LOSS_LIMIT * 0.25:
        status = "DANGER"
        status_color = "red"
    elif daily_risk_remaining < DAILY_LOSS_LIMIT * 0.5:
        status = "CAUTION"
        status_color = "yellow"
    elif payout_ready and current_balance >= SAFE_PAYOUT_TRIGGER:
        status = "PAYOUT READY"
        status_color = "green"
    elif payout_ready:
        status = "ABOVE THRESHOLD"
        status_color = "blue"
    else:
        status = "BUILDING"
        status_color = "green"

    return {
        "current_balance": round(current_balance, 2),
        "prev_close_balance": round(prev_close_balance, 2),
        "trailing_floor": round(floor, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_risk_remaining": round(daily_risk_remaining, 2),
        "daily_risk_used": round(DAILY_LOSS_LIMIT - daily_risk_remaining, 2),
        "daily_risk_pct_used": round((DAILY_LOSS_LIMIT - daily_risk_remaining) / DAILY_LOSS_LIMIT * 100, 1),
        "floor_trailing": floor < TRAIL_FLOOR_STOPS_AT,
        "floor_locked": floor >= TRAIL_FLOOR_STOPS_AT,
        "payout_ready": payout_ready,
        "payout_threshold": PAYOUT_THRESHOLD,
        "safe_payout_trigger": SAFE_PAYOUT_TRIGGER,
        "to_payout_threshold": round(to_payout, 2),
        "to_safe_trigger": round(to_safe_trigger, 2),
        "max_payout": MAX_PAYOUT,
        "safe_after_payout": SAFE_AFTER_PAYOUT,
        "days_at_300": days_needed(300),
        "days_at_400": days_needed(400),
        "days_at_500": days_needed(500),
        "status": status,
        "status_color": status_color,
        "rules": {
            "starting_balance": STARTING_BALANCE,
            "daily_loss_limit": DAILY_LOSS_LIMIT,
            "trail_stops_at": TRAIL_FLOOR_STOPS_AT,
            "payout_threshold": PAYOUT_THRESHOLD,
            "max_payout": MAX_PAYOUT,
        }
    }


def size_position(
    instrument: str,
    stop_points: float,
    account_status: dict,
    risk_per_trade_pct: float = 0.15,  # % of daily risk remaining per trade
    max_risk_per_trade: float = 150.0,
) -> dict:
    """
    Calculate position size for a given instrument and stop distance.

    Args:
        instrument: MNQ, MES, or MGC
        stop_points: Distance from entry to stop loss in points
        account_status: Output of calc_account_status()
        risk_per_trade_pct: Fraction of daily_risk_remaining to risk per trade
        max_risk_per_trade: Absolute cap on per-trade risk
    """
    spec = INSTRUMENTS.get(instrument.upper())
    if not spec or stop_points <= 0:
        return {"error": "Invalid instrument or stop distance"}

    daily_risk_remaining = account_status.get("daily_risk_remaining", 0)
    if daily_risk_remaining <= 0:
        return {
            "instrument": instrument,
            "contracts": 0,
            "risk_amount": 0,
            "note": "No daily risk remaining — stop trading today.",
        }

    # Risk amount for this trade
    risk_amount = min(
        daily_risk_remaining * risk_per_trade_pct,
        max_risk_per_trade,
        daily_risk_remaining * 0.5,   # never more than 50% of remaining in one trade
    )

    dollars_per_point = spec["dollars_per_point"]
    risk_per_contract = stop_points * dollars_per_point
    contracts = max(1, int(risk_amount / risk_per_contract)) if risk_per_contract > 0 else 1

    actual_risk = contracts * risk_per_contract

    # TP levels
    tp_levels = {}
    for r, label in [(1.5, "1.5R"), (2.0, "2R"), (2.5, "2.5R"), (3.0, "3R")]:
        tp_pts = round(stop_points * r, 2)
        tp_gain = round(tp_pts * dollars_per_point * contracts, 2)
        tp_levels[label] = {"points": tp_pts, "gain": tp_gain}

    return {
        "instrument": instrument.upper(),
        "instrument_name": spec["name"],
        "dollars_per_point": dollars_per_point,
        "stop_points": stop_points,
        "risk_per_contract": round(risk_per_contract, 2),
        "risk_amount": round(actual_risk, 2),
        "contracts": contracts,
        "tp_levels": tp_levels,
        "note": f"{contracts} contract{'s' if contracts != 1 else ''} · ${actual_risk:.0f} risk · stop {stop_points} pts",
        "daily_risk_after_trade": round(daily_risk_remaining - actual_risk, 2),
    }


def daily_trade_plan(account_status: dict, instrument: str = "MNQ") -> dict:
    """Generate a simple daily trade plan based on account state."""
    remaining = account_status.get("daily_risk_remaining", 0)
    status = account_status.get("status", "")
    to_trigger = account_status.get("to_safe_trigger", 0)

    if status == "BLOWN":
        return {"recommendation": "STOP — daily loss limit hit. No more trades today.", "max_trades": 0}
    if status == "DANGER":
        return {"recommendation": "Extreme caution. 1 trade max. Reduce size by 50%.", "max_trades": 1}

    # How many trades at standard size can we take?
    risk_per_trade = min(remaining * 0.15, 150)
    max_trades = int(remaining / risk_per_trade) if risk_per_trade > 0 else 0
    daily_goal = min(300, to_trigger) if to_trigger > 0 else 300

    return {
        "recommendation": f"Target ${daily_goal:.0f} today. Max {min(max_trades, 3)} high-quality trades.",
        "max_trades": min(max_trades, 3),
        "risk_per_trade": round(risk_per_trade, 2),
        "daily_goal": daily_goal,
        "primary_instrument": instrument,
        "note": "Only take A+ ICT setups. Killzone only. Stop when daily goal hit.",
    }
