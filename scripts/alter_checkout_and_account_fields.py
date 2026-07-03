import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.base import engine


STATEMENTS = [
    "ALTER TABLE components ADD COLUMN IF NOT EXISTS short_description TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_type VARCHAR(16)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_address TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_comment TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_time_from VARCHAR(5)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_time_to VARCHAR(5)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_comment TEXT",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS admin_comment TEXT",
    """
    CREATE TABLE IF NOT EXISTS calendar_days (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL UNIQUE,
        status VARCHAR(16) NOT NULL DEFAULT 'available',
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
]


async def main():
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))
    print("Поля оформления заказа, личного кабинета и календаря обновлены")


if __name__ == "__main__":
    asyncio.run(main())
