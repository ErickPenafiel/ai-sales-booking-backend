"""
Drop all tables, recreate schema and run seed.
Run inside venv:
    python scripts/reset_and_seed.py
"""
import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.base import Base

load_dotenv(override=True)

async def main():
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    print("Using DB URL:", database_url)
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    print("Running seed...")
    # run seed script
    from scripts import seed
    await seed.main()
    print("Reset, migration and seeding complete.")

if __name__ == '__main__':
    asyncio.run(main())
