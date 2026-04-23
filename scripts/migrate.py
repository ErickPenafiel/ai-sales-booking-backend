"""Create database tables for the FastAPI service using SQLAlchemy models.

This script uses the `DATABASE_URL` env var. If it contains an asyncpg driver
suffix (+asyncpg) it will be stripped to create a sync engine for migrations.

Run inside project venv:
    python scripts/migrate.py
"""
import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import app.models  # noqa: F401
from app.models.base import Base

load_dotenv(override=True)


async def _add_columns(database_url: str) -> None:
    """Add new provider_id columns to existing tables."""
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("""
                ALTER TABLE services ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES providers(id) ON DELETE CASCADE
            """))
            print("Added provider_id to services")
        except Exception as e:
            print(f"services already has provider_id or error: {e}")

        try:
            await conn.execute(text("""
                ALTER TABLE availabilities ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES providers(id) ON DELETE CASCADE
            """))
            print("Added provider_id to availabilities")
        except Exception as e:
            print(f"availabilities already has provider_id or error: {e}")

        try:
            await conn.execute(text("""
                ALTER TABLE appointments ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES providers(id) ON DELETE CASCADE
            """))
            print("Added provider_id to appointments")
        except Exception as e:
            print(f"appointments already has provider_id or error: {e}")

        await conn.commit()
    await engine.dispose()


async def _create_tables_async(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:dotaallstarsv.25@127.0.0.1:5433/ai_sales")
    print("Using DB URL for migrations:", database_url)

    print("\nStep 1: Adding new columns to existing tables...")
    asyncio.run(_add_columns(database_url))

    print("\nStep 2: Creating new tables...")
    asyncio.run(_create_tables_async(database_url))
    print("Migrations complete (tables created).")


if __name__ == "__main__":
    main()
