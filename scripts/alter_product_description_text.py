import asyncio
import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE products ALTER COLUMN description TYPE TEXT"))
    print("products.description расширено до TEXT")


if __name__ == "__main__":
    asyncio.run(main())
