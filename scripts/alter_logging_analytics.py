import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.base import engine


STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS funnel_events (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        session_id INTEGER NULL REFERENCES user_sessions(id) ON DELETE SET NULL,
        event_type VARCHAR(64) NOT NULL,
        step VARCHAR(64),
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_funnel_events_user ON funnel_events(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_funnel_events_type ON funnel_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_funnel_events_created ON funnel_events(created_at)",
]


async def main():
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))
    print("Логирование воронки и аналитика обновлены")


if __name__ == "__main__":
    asyncio.run(main())
