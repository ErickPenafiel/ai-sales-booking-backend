import asyncio
from uuid import UUID
from app.db.session import SessionLocal
from app.models.resource import Resource
from sqlalchemy import select

async def main():
    tenant_id = UUID("7cdfc021-20e5-48d7-bae1-9673e4f154a6")
    async with SessionLocal() as session:
        rows = await session.scalars(select(Resource).where(Resource.tenant_id == tenant_id))
        resources = list(rows)
        print("Found resources:", len(resources))
        for r in resources:
            print(r.id, r.name)

if __name__ == '__main__':
    asyncio.run(main())
