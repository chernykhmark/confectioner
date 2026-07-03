import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import engine, Base
import db.models  # noqa: F401 — регистрирует все модели в metadata


async def init_db(drop: bool = False):
    async with engine.begin() as conn:
        if drop:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Схема БД создана")


if __name__ == "__main__":
    asyncio.run(init_db(drop="--drop" in sys.argv))