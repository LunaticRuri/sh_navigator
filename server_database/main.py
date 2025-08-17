from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional
from server_backend.database.database_pool import AsyncConnectionPool  # 초기엔 재사용
import aiosqlite

app = FastAPI(
    title="Database Service",
    description="DB 전용 FastAPI 서비스",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 내부 통신만이면 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "/Users/nuriseok/sh_navigator/data/libraries.db")
POOL_MAX = int(os.getenv("DB_POOL_MAX", "20"))
POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))

pool: Optional[AsyncConnectionPool] = None

@app.on_event("startup")
async def startup():
    global pool
    pool = AsyncConnectionPool(DB_PATH, max_connections=POOL_MAX, min_connections=POOL_MIN)
    await pool.initialize_pool()

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close_all_connections()

@app.get("/health")
async def health():
    if not pool:
        return {"status": "uninitialized"}
    status = await pool.get_pool_status()
    return {"status": "ok" if status.get("initialized") else "bad", "pool": status}

@app.get("/db/books/isbn/{isbn}")
async def get_book_by_isbn(isbn: str):
    try:
        async with pool.get_connection() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM books WHERE isbn = ?", (isbn,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Book not found")
            return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))