import aiosqlite
import json
import os

DB_PATH = os.getenv("DATABASE_URL", "./terminal.db")

CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        data TEXT NOT NULL,
        provider TEXT DEFAULT 'yahoo'
    )""",
    """CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT DEFAULT 'MNQ',
        direction TEXT,
        entry REAL,
        exit REAL,
        result REAL,
        r_multiple REAL,
        setup_type TEXT,
        bias_at_entry TEXT,
        confidence INTEGER,
        notes TEXT,
        mistake_tag TEXT,
        lesson TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS wave_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        call_wave REAL,
        put_wave REAL,
        net_wave REAL,
        qqq_price REAL
    )""",
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_TABLES:
            await db.execute(stmt)
        await db.commit()


async def save_snapshot(data: dict, provider: str = "yahoo"):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO snapshots (timestamp, data, provider) VALUES (?,?,?)",
            (ts, json.dumps(data), provider),
        )
        await db.commit()
    return ts


async def get_snapshots(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, timestamp, provider FROM snapshots ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_snapshot_by_id(snapshot_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM snapshots WHERE id=?", (snapshot_id,)
        ) as cur:
            row = await cur.fetchone()
    if row:
        d = dict(row)
        d["data"] = json.loads(d["data"])
        return d
    return None


async def save_wave_point(call_wave: float, put_wave: float, net_wave: float, qqq_price: float):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO wave_history (timestamp, call_wave, put_wave, net_wave, qqq_price) VALUES (?,?,?,?,?)",
            (ts, call_wave, put_wave, net_wave, qqq_price),
        )
        await db.commit()


async def get_wave_history(limit: int = 60):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wave_history ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return list(reversed([dict(r) for r in rows]))


async def save_trade(trade: dict):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO trades
               (timestamp,symbol,direction,entry,exit,result,r_multiple,setup_type,bias_at_entry,confidence,notes,mistake_tag,lesson)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts,
                trade.get("symbol", "MNQ"),
                trade.get("direction"),
                trade.get("entry"),
                trade.get("exit"),
                trade.get("result"),
                trade.get("r_multiple"),
                trade.get("setup_type"),
                trade.get("bias_at_entry"),
                trade.get("confidence"),
                trade.get("notes"),
                trade.get("mistake_tag"),
                trade.get("lesson"),
            ),
        )
        await db.commit()


async def get_trades(limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
