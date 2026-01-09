import aiosqlite
from typing import Optional, List, Dict, Any

DB_PATH = "rawwow.sqlite3"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            service TEXT NOT NULL,
            comment TEXT,
            photo_file_id TEXT NOT NULL,
            photo_type TEXT,
            photo_name TEXT,
            ref_file_id TEXT,
            ref_type TEXT,
            status TEXT NOT NULL DEFAULT 'new'
        );
        """)
        await db.commit()


async def create_order(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    service: str,
    comment: str,
    photo_file_id: str,
    photo_type: Optional[str] = None,
    photo_name: Optional[str] = None,
    ref_file_id: Optional[str] = None,
    ref_type: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO orders (
                user_id, username, full_name, service, comment,
                photo_file_id, photo_type, photo_name,
                ref_file_id, ref_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, username, full_name, service, comment,
            photo_file_id, photo_type, photo_name,
            ref_file_id, ref_type
        ))
        await db.commit()
        return cur.lastrowid


async def list_orders(limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT id, created_at, user_id, username, full_name, service, status FROM orders"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_order_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()
