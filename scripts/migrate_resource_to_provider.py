"""
Migration script to copy Resource data to Provider and update tables.

This script:
1. Creates providers from existing resources (1:1 copy)
2. Copies resource_id data to provider_id in services, availabilities, appointments
3. Drops old resource_id columns

Run: python scripts/migrate_resource_to_provider.py
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:dotaallstarsv.25@127.0.0.1:5433/ai_sales")


async def migrate_resources_to_providers():
    """Create providers from existing resources (1:1 copy)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    engine = create_async_engine(DATABASE_URL, future=True)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO providers (id, tenant_id, name, kind, config, created_at, updated_at)
            SELECT id, tenant_id, name, kind, metadata, created_at, updated_at
            FROM resources
            ON CONFLICT (id) DO NOTHING
            RETURNING id
        """))
        created = result.rowcount if result.returns_rows else 0
        print(f"Created {created} providers from resources")

    await engine.dispose()


async def migrate_services():
    """Copy resource_id to provider_id in services table."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(DATABASE_URL, future=True)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            UPDATE services s
            SET provider_id = r.id
            FROM resources r
            WHERE s.resource_id = r.id
            AND s.provider_id IS NULL
        """))
        await conn.commit()
        print(f"Updated {result.rowcount} services to use provider_id")

    await engine.dispose()


async def migrate_availabilities():
    """Copy resource_id to provider_id in availabilities table."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(DATABASE_URL, future=True)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            UPDATE availabilities a
            SET provider_id = r.id
            FROM resources r
            WHERE a.resource_id = r.id
            AND a.provider_id IS NULL
        """))
        await conn.commit()
        print(f"Updated {result.rowcount} availabilities to use provider_id")

    await engine.dispose()


async def migrate_appointments():
    """Copy resource_id to provider_id in appointments table."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(DATABASE_URL, future=True)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            UPDATE appointments a
            SET provider_id = r.id
            FROM resources r
            WHERE a.resource_id = r.id
            AND a.provider_id IS NULL
        """))
        await conn.commit()
        print(f"Updated {result.rowcount} appointments to use provider_id")

    await engine.dispose()


async def drop_old_columns():
    """Drop old resource_id columns after migration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(DATABASE_URL, future=True)

    async with engine.begin() as conn:
        try:
            await conn.execute(text("""
                ALTER TABLE services DROP COLUMN IF EXISTS resource_id
            """))
            print("Dropped resource_id from services")
        except Exception as e:
            print(f"Error dropping from services: {e}")

        try:
            await conn.execute(text("""
                ALTER TABLE availabilities DROP COLUMN IF EXISTS resource_id
            """))
            print("Dropped resource_id from availabilities")
        except Exception as e:
            print(f"Error dropping from availabilities: {e}")

        try:
            await conn.execute(text("""
                ALTER TABLE appointments DROP COLUMN IF EXISTS resource_id
            """))
            print("Dropped resource_id from appointments")
        except Exception as e:
            print(f"Error dropping from appointments: {e}")

        await conn.commit()

    await engine.dispose()


async def main():
    print("Starting Resource -> Provider migration...")
    print("=" * 50)

    print("\n1. Creating providers from resources...")
    await migrate_resources_to_providers()

    print("\n2. Migrating services...")
    await migrate_services()

    print("\n3. Migrating availabilities...")
    await migrate_availabilities()

    print("\n4. Migrating appointments...")
    await migrate_appointments()

    print("\n5. Dropping old resource_id columns...")
    await drop_old_columns()

    print("\n" + "=" * 50)
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())