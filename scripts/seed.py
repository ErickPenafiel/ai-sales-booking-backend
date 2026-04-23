"""Async seeder to populate Postgres (SQLAlchemy) and Qdrant with demo data.

Run inside project venv:
    python scripts/seed.py

The script will:
 - create a tenant, resource, service, availability and a sample appointment
 - seed Qdrant collection with two documents tied to the tenant
 - write placeholder media files into ./media and register them in DB
"""
import asyncio
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from dotenv import load_dotenv

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
import sqlalchemy as sa
from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.resource import Resource
from app.models.service import Service
from app.models.availability import Availability
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.media import Media

load_dotenv(override=True)


async def main() -> None:
    # Attempt DB seeding; if DB is not available, continue to Qdrant/media seeding.
    tenant = None

    # Prepare DB connection: try configured DATABASE_URL, otherwise fallback to local sqlite file.
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    async_engine = None
    SessionLocalLocal = None

    # Try to use the configured async DB URL; on failure, fallback to sqlite file-based DB.
    try:
        async_engine = create_async_engine(database_url)
        SessionLocalLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
        # quick test connect
        async with async_engine.connect() as conn:
            await conn.run_sync(lambda sync_conn: None)
        # If using sqlite, ensure tables exist by creating them via a sync engine
        if "sqlite" in database_url:
            sqlite_db = Path("dev.db").absolute()
            sync_sqlite_url = f"sqlite:///{sqlite_db}"
            sync_engine = create_engine(sync_sqlite_url, future=True)
            for table in Base.metadata.tables.values():
                for col in table.columns:
                    if type(col.type).__name__ == "JSONB":
                        col.type = sa.JSON()
            Base.metadata.create_all(sync_engine)
    except Exception as exc:
        print("Primary DB connect failed, falling back to sqlite. Error:", exc)
        sqlite_db = Path("dev.db").absolute()
        sync_sqlite_url = f"sqlite:///{sqlite_db}"
        # create sync engine and tables
        sync_engine = create_engine(sync_sqlite_url, future=True)
        # Replace PostgreSQL-specific types (JSONB) with SQLite-compatible types (JSON)
        for table in Base.metadata.tables.values():
            for col in table.columns:
                if type(col.type).__name__ == "JSONB":
                    col.type = sa.JSON()
        Base.metadata.create_all(sync_engine)
        # use async wrapper for sqlite
        database_url = f"sqlite+aiosqlite:///{sqlite_db}"
        async_engine = create_async_engine(database_url)
        SessionLocalLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

    try:
        async with SessionLocalLocal() as session:
            # create or fetch tenant
            tenant = await session.scalar(select(Tenant).where(Tenant.slug == "demo-tenant"))
            if tenant is None:
                tenant = Tenant(name="Demo Tenant", slug="demo-tenant", contact_email="demo@example.com")
                session.add(tenant)
                await session.flush()

            # create or fetch resource and service
            resource = await session.scalar(
                select(Resource).where(Resource.tenant_id == tenant.tenant_id, Resource.name == "Dr. Demo")
            )
            if resource is None:
                resource = Resource(
                    tenant_id=tenant.tenant_id,
                    name="Dr. Demo",
                    kind="provider",
                    resource_metadata={"specialty": "general"},
                )
                session.add(resource)
                await session.flush()

            service = await session.scalar(
                select(Service).where(Service.tenant_id == tenant.tenant_id, Service.name == "Consultation")
            )
            if service is None:
                service = Service(
                    tenant_id=tenant.tenant_id,
                    resource_id=resource.id,
                    name="Consultation",
                    duration_minutes=30,
                    price_amount=50.0,
                )
                session.add(service)
                await session.flush()

            # create availability if missing for today weekday
            day_of_week = date.today().weekday()
            avail = await session.scalar(
                select(Availability).where(
                    Availability.tenant_id == tenant.tenant_id,
                    Availability.resource_id == resource.id,
                    Availability.day_of_week == day_of_week,
                    Availability.start_time == time(9, 0),
                    Availability.end_time == time(17, 0),
                )
            )
            if avail is None:
                avail = Availability(
                    tenant_id=tenant.tenant_id,
                    resource_id=resource.id,
                    day_of_week=day_of_week,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                )
                session.add(avail)
                await session.flush()

            # create sample appointment if there is none
            # Appointment columns are timestamp without timezone in this schema.
            start = datetime.utcnow() + timedelta(days=1, hours=1)
            appt = await session.scalar(
                select(Appointment).where(
                    Appointment.tenant_id == tenant.tenant_id,
                    Appointment.customer_phone == "+10000000000",
                )
            )
            if appt is None:
                appt = Appointment(
                    tenant_id=tenant.tenant_id,
                    resource_id=resource.id,
                    service_id=service.id,
                    customer_name="Test Customer",
                    customer_phone="+10000000000",
                    start_at=start,
                    end_at=start + timedelta(minutes=service.duration_minutes),
                    total_amount=service.price_amount,
                    currency=service.currency,
                    status="PENDING_PAYMENT",
                )
                session.add(appt)
                await session.flush()

            # Ensure larger dataset for load testing.
            target_appointments = int(os.getenv("SEED_APPOINTMENTS_TARGET", "120"))
            existing_ids = await session.scalars(select(Appointment.id).where(Appointment.tenant_id == tenant.tenant_id))
            existing_count = len(list(existing_ids))
            if existing_count < target_appointments:
                to_create = target_appointments - existing_count
                base_day = date.today() - timedelta(days=20)
                slot_times = [time(9, 0), time(9, 30), time(10, 0), time(10, 30), time(14, 0), time(14, 30)]
                created = 0
                day_cursor = 0
                while created < to_create:
                    day = base_day + timedelta(days=day_cursor)
                    day_cursor += 1
                    if day.weekday() >= 5:
                        continue
                    for slot_t in slot_times:
                        if created >= to_create:
                            break
                        idx = existing_count + created + 1
                        phone = f"+1000{idx:07d}"
                        local_start = datetime.combine(day, slot_t)
                        start_at = local_start
                        end_at = start_at + timedelta(minutes=service.duration_minutes)
                        exists = await session.scalar(
                            select(Appointment).where(
                                Appointment.tenant_id == tenant.tenant_id,
                                Appointment.customer_phone == phone,
                                Appointment.start_at == start_at,
                            )
                        )
                        if exists is not None:
                            continue
                        session.add(
                            Appointment(
                                tenant_id=tenant.tenant_id,
                                resource_id=resource.id,
                                service_id=service.id,
                                customer_name=f"Load Customer {idx}",
                                customer_phone=phone,
                                start_at=start_at,
                                end_at=end_at,
                                total_amount=service.price_amount,
                                currency=service.currency,
                                status="CONFIRMED",
                            )
                        )
                        created += 1

            # create media folder and write placeholders
            media_dir = Path("media")
            media_dir.mkdir(exist_ok=True)
            samples = {
                "sample.jpg": b"\xFF\xD8\xFF\xE0" + b"JPEGPLACEHOLDER",
                "sample.pdf": b"%PDF-1.4\n%PDFPLACEHOLDER",
                "sample.mp3": b"ID3MP3PLACEHOLDER",
                "sample.mp4": b"MP4PLACEHOLDER",
            }
            for name, content in samples.items():
                path = media_dir / name
                path.write_bytes(content)
                existing_media = await session.scalar(
                    select(Media).where(Media.tenant_id == tenant.tenant_id, Media.filename == name)
                )
                if existing_media is None:
                    media = Media(tenant_id=tenant.tenant_id, filename=name, content_type=None, path=str(path))
                    session.add(media)
            await session.commit()
    except Exception as exc:
        print("DB seeding failed, continuing with media/Qdrant seeding. Error:", exc)
        # Ensure media files still exist even if DB failed
        media_dir = Path("media")
        media_dir.mkdir(exist_ok=True)
        samples = {
            "sample.jpg": b"\xFF\xD8\xFF\xE0" + b"JPEGPLACEHOLDER",
            "sample.pdf": b"%PDF-1.4\n%PDFPLACEHOLDER",
            "sample.mp3": b"ID3MP3PLACEHOLDER",
            "sample.mp4": b"MP4PLACEHOLDER",
        }
        for name, content in samples.items():
            path = media_dir / name
            if not path.exists():
                path.write_bytes(content)

    # seed qdrant
    q = AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), api_key=os.getenv("QDRANT_API_KEY"))
    collection = os.getenv("QDRANT_COLLECTION", "tenant_knowledge")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "qdrant").strip().lower()
    qdrant_embedding_model = os.getenv("QDRANT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    qdrant_vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "1536"))
    # ensure collection exists
    try:
        await q.get_collection(collection_name=collection)
    except Exception:
        await q.recreate_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=qdrant_vector_size, distance=qmodels.Distance.COSINE),
        )

    tenant_id_str = str(tenant.tenant_id) if tenant is not None else "demo-tenant"
    docs = [
        "Welcome to Demo Tenant's knowledge base.",
        "Our cancellation policy: 24h notice.",
    ]

    def _dense_points() -> list[qmodels.PointStruct]:
        return [
            qmodels.PointStruct(
                id=uuid4().hex,
                vector=[0.01 + (index * 0.01)] * qdrant_vector_size,
                payload={"text": text, "metadata": {"tenant_id": tenant_id_str}},
            )
            for index, text in enumerate(docs)
        ]

    if embedding_provider == "qdrant":
        inference_points = [
            qmodels.PointStruct(
                id=uuid4().hex,
                vector=qmodels.Document(text=text, model=qdrant_embedding_model),
                payload={"text": text, "metadata": {"tenant_id": tenant_id_str}},
            )
            for text in docs
        ]
        try:
            await q.upsert(collection_name=collection, points=inference_points)
        except Exception as exc:
            if "not found among supported models" in str(exc):
                print(
                    "Qdrant inference model unsupported for seeding; "
                    "falling back to dense vectors.",
                    "Model:",
                    qdrant_embedding_model,
                )
                await q.upsert(collection_name=collection, points=_dense_points())
            else:
                raise
    else:
        await q.upsert(collection_name=collection, points=_dense_points())

    print("Seeding complete. Tenant:", tenant_id_str)


if __name__ == "__main__":
    asyncio.run(main())
