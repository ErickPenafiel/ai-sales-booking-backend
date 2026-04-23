from __future__ import annotations

import json
import logging
from datetime import date, datetime, time as time_type
from typing import Any
from uuid import UUID

from langchain.tools import tool
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.provider import Provider
from app.models.service import Service
from app.services import crud_service
from app.services.slot_service import calculate_available_slots, SlotCalculationError
from app.services import tracing

logger = logging.getLogger(__name__)


@tool
@tracing.langsmith_traceable(run_type="tool", name="get_providers_and_services")
async def get_providers_and_services(tenant_id: str) -> str:
    """Get all providers and their services for a tenant. Returns JSON with providers and their services.

    This tool returns a complete catalog of available professionals and services.
    Use this FIRST when user wants to book an appointment to present options.

    Security: tenant_id must be provided and is always used to scope the DB query.
    """
    logger.info("Tool(get_providers_and_services) called tenant_id=%s", tenant_id)
    tracing.record_trace({"kind": "tool", "tool": "get_providers_and_services", "stage": "start", "tenant_id": tenant_id})
    try:
        tid = UUID(tenant_id)
    except Exception:
        logger.warning("Tool(get_providers_and_services) invalid tenant_id=%s", tenant_id)
        return json.dumps({"error": "invalid_tenant_id"})

    async with SessionLocal() as session:
        try:
            providers_rows = await session.scalars(
                select(Provider).where(Provider.tenant_id == tid).order_by(Provider.name.asc())
            )

            providers = []
            for provider in providers_rows:
                services_rows = await session.scalars(
                    select(Service)
                    .where(Service.tenant_id == tid, Service.provider_id == provider.id)
                    .order_by(Service.name.asc())
                )
                services = [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "duration_minutes": s.duration_minutes,
                        "price_amount": float(s.price_amount),
                        "currency": s.currency,
                        "description": s.description,
                    }
                    for s in services_rows
                ]
                providers.append({
                    "id": str(provider.id),
                    "name": provider.name,
                    "kind": provider.kind,
                    "services": services,
                })

            out = {
                "tenant_id": tenant_id,
                "providers": providers,
                "total_providers": len(providers),
                "total_services": sum(len(p["services"]) for p in providers),
            }
            logger.info("Tool(get_providers_and_services) returning %s providers for tenant=%s", len(providers), tenant_id)
            tracing.record_trace({
                "kind": "tool",
                "tool": "get_providers_and_services",
                "stage": "end",
                "tenant_id": tenant_id,
                "providers_count": len(providers)
            })
            return json.dumps(out)
        except Exception as exc:
            logger.exception("get_providers_and_services failed for tenant=%s", tenant_id, exc_info=exc)
            tracing.record_trace({"kind": "tool", "tool": "get_providers_and_services", "stage": "error", "tenant_id": tenant_id, "error": str(exc)})
            return json.dumps({"error": "internal_error"})


@tool
@tracing.langsmith_traceable(run_type="tool", name="get_provider_slots")
async def get_provider_slots(*, tenant_id: str, provider_id: str, service_id: str, date: str) -> str:
    """Get available time slots for a provider and service on a specific date.

    REQUIRED PARAMETERS:
    - tenant_id: Tenant UUID
    - provider_id: Provider UUID (from get_providers_and_services)
    - service_id: Service UUID (from get_providers_and_services)
    - date: Date in YYYY-MM-DD format

    Returns JSON with available time slots in HH:MM format.

    IMPORTANT: You MUST have BOTH provider_id AND service_id before calling this tool.
    """
    logger.info("Tool(get_provider_slots) called tenant_id=%s provider_id=%s service_id=%s date=%s", tenant_id, provider_id, service_id, date)
    tracing.record_trace({
        "kind": "tool",
        "tool": "get_provider_slots",
        "stage": "start",
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "service_id": service_id,
        "date": date
    })
    try:
        tid = UUID(tenant_id)
        pid = UUID(provider_id)
        sid = UUID(service_id)
    except Exception:
        logger.warning("Tool(get_provider_slots) invalid UUIDs tenant=%s provider=%s service=%s", tenant_id, provider_id, service_id)
        return json.dumps({"error": "invalid_uuid", "message": "provider_id and service_id must be valid UUIDs"})

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        try:
            target_date = datetime.fromisoformat(date.split("T")[0]).date()
        except Exception:
            return json.dumps({"error": "invalid_date_format", "message": "Date must be in YYYY-MM-DD format"})

    async with SessionLocal() as session:
        try:
            slots = await calculate_available_slots(
                session=session,
                tenant_id=tid,
                provider_id=pid,
                service_id=sid,
                target_date=target_date,
            )

            logger.info("Tool(get_provider_slots) retrieved %s slots for tenant=%s provider=%s service=%s date=%s",
                len(slots), tenant_id, provider_id, service_id, target_date.isoformat())
            tracing.record_trace({
                "kind": "tool",
                "tool": "get_provider_slots",
                "stage": "end",
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "service_id": service_id,
                "date": target_date.isoformat(),
                "slots_count": len(slots),
                "slots": slots
            })

            out = {
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "service_id": service_id,
                "date": target_date.isoformat(),
                "available_slots": slots,
                "has_availability": len(slots) > 0,
            }
            return json.dumps(out)
        except SlotCalculationError as exc:
            logger.warning("Tool(get_provider_slots) no availability for tenant=%s provider=%s date=%s", tenant_id, provider_id, date)
            tracing.record_trace({"kind": "tool", "tool": "get_provider_slots", "stage": "no_availability", "tenant_id": tenant_id, "provider_id": provider_id, "date": date})
            return json.dumps({
                "error": "no_availability",
                "message": str(exc),
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "service_id": service_id,
                "date": date,
                "available_slots": [],
                "has_availability": False,
            })
        except Exception as exc:
            logger.exception("get_provider_slots failed tenant=%s provider=%s date=%s", tenant_id, provider_id, date, exc_info=exc)
            tracing.record_trace({"kind": "tool", "tool": "get_provider_slots", "stage": "error", "tenant_id": tenant_id, "provider_id": provider_id, "date": date, "error": str(exc)})
            return json.dumps({"error": "internal_error", "message": str(exc)})


@tool
@tracing.langsmith_traceable(run_type="tool", name="create_booking")
async def create_booking(
    *,
    tenant_id: str,
    provider_id: str,
    service_id: str,
    date: str,
    time: str,
    customer_name: str,
    customer_phone: str,
    customer_ci: str,
) -> str:
    """Create a booking/appointment in DB.

    REQUIRED PARAMETERS:
    - tenant_id: Tenant UUID
    - provider_id: Provider UUID
    - service_id: Service UUID (required - booking will fail without it)
    - date: Date in YYYY-MM-DD format
    - time: Start time in HH:MM format
    - customer_name: Full name of the customer
    - customer_phone: Phone number
    - customer_ci: Identification document number (CI, passport, etc.)

    Returns JSON with booking confirmation or error.
    """
    logger.info(
        "Tool(create_booking) called tenant_id=%s provider_id=%s service_id=%s date=%s time=%s customer_name=%s customer_ci=%s",
        tenant_id, provider_id, service_id, date, time, customer_name, customer_ci,
    )
    tracing.record_trace({
        "kind": "tool",
        "tool": "create_booking",
        "stage": "start",
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "service_id": service_id,
        "date": date,
        "time": time
    })

    try:
        tid = UUID(tenant_id)
        pid = UUID(provider_id)
        sid = UUID(service_id)
    except Exception:
        logger.warning("Tool(create_booking) invalid UUIDs tenant_id=%s provider_id=%s service_id=%s", tenant_id, provider_id, service_id)
        return json.dumps({"error": "invalid_uuid", "message": "tenant_id, provider_id, and service_id must be valid UUIDs"})

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        logger.warning("Tool(create_booking) invalid date=%s", date)
        return json.dumps({"error": "invalid_date_format", "message": "Date must be in YYYY-MM-DD format"})

    try:
        slot_time = datetime.strptime(time.strip(), "%H:%M").time()
    except Exception:
        logger.warning("Tool(create_booking) invalid time=%s", time)
        return json.dumps({"error": "invalid_time_format", "message": "Time must be in HH:MM format"})

    if not customer_name.strip():
        return json.dumps({"error": "missing_customer_name", "message": "Customer name is required"})

    if not customer_phone.strip():
        return json.dumps({"error": "missing_customer_phone", "message": "Customer phone is required"})

    if not customer_ci.strip():
        return json.dumps({"error": "missing_customer_ci", "message": "Customer identification (CI) is required"})

    async with SessionLocal() as session:
        try:
            service = await session.scalar(
                select(Service)
                .where(Service.id == sid, Service.tenant_id == tid)
            )
            if service is None:
                return json.dumps({"error": "service_not_found", "message": f"Service {service_id} not found"})

            start_datetime = datetime.combine(target_date, slot_time)
            end_datetime = datetime.combine(target_date, slot_time)
            from datetime import timedelta
            end_datetime = end_datetime + timedelta(minutes=service.duration_minutes)
            end_time = end_datetime.time()

            appointment = await crud_service.create_appointment(
                session,
                tenant_id=tid,
                provider_id=pid,
                service_id=sid,
                customer_name=customer_name.strip(),
                customer_phone=customer_phone.strip(),
                date=target_date,
                start_time=slot_time,
                end_time=end_time,
                notes=json.dumps({"customer_ci": customer_ci.strip()}, ensure_ascii=True),
                total_amount=float(service.price_amount),
                currency=service.currency,
            )
            await session.commit()

            logger.info(
                "Tool(create_booking) booking persisted appointment_id=%s tenant=%s provider=%s service=%s",
                appointment.id, tenant_id, provider_id, service_id,
            )
            tracing.record_trace({
                "kind": "tool",
                "tool": "create_booking",
                "stage": "end",
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "service_id": service_id,
                "booking_id": str(appointment.id)
            })
            return json.dumps(
                {
                    "success": True,
                    "tenant_id": tenant_id,
                    "provider_id": provider_id,
                    "service_id": service_id,
                    "service_name": service.name,
                    "date": date,
                    "time": time,
                    "end_time": end_time.strftime("%H:%M"),
                    "duration_minutes": service.duration_minutes,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "customer_ci": customer_ci,
                    "booking_id": str(appointment.id),
                    "total_amount": float(service.price_amount),
                    "currency": service.currency,
                    "status": "CONFIRMED",
                }
            )
        except Exception as exc:
            await session.rollback()
            logger.exception("create_booking failed tenant=%s provider=%s", tenant_id, provider_id, exc_info=exc)
            tracing.record_trace({
                "kind": "tool",
                "tool": "create_booking",
                "stage": "error",
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "service_id": service_id,
                "error": str(exc)
            })
            error_msg = str(exc)
            if "already exists" in error_msg.lower() or "conflict" in error_msg.lower():
                return json.dumps({
                    "error": "slot_unavailable",
                    "message": "This time slot is no longer available. Please select another time."
                })
            return json.dumps({"error": "internal_error", "message": error_msg})


@tool
@tracing.langsmith_traceable(run_type="tool", name="search_business_knowledge")
async def search_business_knowledge(*, tenant_id: str, query: str) -> str:
    """Search business knowledge base (prices, location, photos, manuals, FAQs).

    Returns text_context for LLM response and media_attachments for WhatsApp.
    Use when user asks about: prices, costs, location, directions, photos, gallery,
    results, services offered, policies, FAQs, manuals, or business info.

    Parameters:
    - tenant_id: Tenant UUID
    - query: User question in natural language
    """
    logger.info("Tool(search_business_knowledge) called tenant_id=%s query=%s", tenant_id, query[:100])
    tracing.record_trace({
        "kind": "tool",
        "tool": "search_business_knowledge",
        "stage": "start",
        "tenant_id": tenant_id,
        "query": query[:200]
    })

    try:
        tid = UUID(tenant_id)
    except Exception:
        logger.warning("Tool(search_business_knowledge) invalid tenant_id=%s", tenant_id)
        return json.dumps({"error": "invalid_tenant_id"})

    qdrant_url = "http://localhost:6333"
    qdrant_api_key = None
    collection = "tenant_knowledge"
    embedding_model = "sentence-transformers/all-MiniLM-L6-v2"

    try:
        qdrant = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        tenant_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.tenant_id",
                    match=qdrant_models.MatchValue(value=str(tid)),
                )
            ]
        )

        result = await qdrant.query_points(
            collection_name=collection,
            query=embedding_model,
            query_filter=tenant_filter,
            limit=10,
            with_payload=True,
        )

        points = result.points if hasattr(result, "points") else []
        search_results = []
        for point in points:
            payload = getattr(point, "payload", {}) or {}
            text = payload.get("text", "") or payload.get("content", "") or payload.get("title", "")
            metadata = payload.get("metadata", {}) or {}

            media = []
            if metadata.get("url"):
                media.append({
                    "url": metadata.get("url"),
                    "type": metadata.get("asset_type", "IMAGE"),
                    "caption": metadata.get("description", "") or metadata.get("title", ""),
                })

            search_results.append({
                "text": text,
                "title": payload.get("title", ""),
                "media": media,
                "score": getattr(point, "score", 1.0),
            })

        search_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = search_results[:5]

        text_context = "\n\n".join(
            f"- {r['title']}: {r['text'][:500]}" if r["title"] else r["text"][:500]
            for r in top_results
        )

        media_attachments = []
        for r in top_results:
            for m in r.get("media", []):
                if m.get("url"):
                    media_attachments.append(m)

        logger.info("Tool(search_business_knowledge) found %s docs, %s media",
                  len(top_results), len(media_attachments))
        tracing.record_trace({
            "kind": "tool",
            "tool": "search_business_knowledge",
            "stage": "end",
            "tenant_id": tenant_id,
            "results_count": len(top_results),
            "media_count": len(media_attachments)
        })

        return json.dumps({
            "text_context": text_context or "No se encontró información relevante.",
            "media_attachments": media_attachments,
            "has_attachments": len(media_attachments) > 0,
            "sources": [r["title"] for r in top_results if r.get("title")],
        })

    except Exception as exc:
        logger.exception("search_business_knowledge failed tenant=%s", tenant_id, exc_info=exc)
        tracing.record_trace({
            "kind": "tool",
            "tool": "search_business_knowledge",
            "stage": "error",
            "tenant_id": tenant_id,
            "error": str(exc)
        })
        return json.dumps({
            "error": "search_failed",
            "text_context": "No pude buscar en la base de conocimiento.",
            "media_attachments": [],
            "has_attachments": False,
        })


_gps = getattr(get_provider_slots, "func", None)
get_provider_slots_func = _gps if callable(_gps) else get_provider_slots

_gpas = getattr(get_providers_and_services, "func", None)
get_providers_and_services_func = _gpas if callable(_gpas) else get_providers_and_services

_cb = getattr(create_booking, "func", None)
create_booking_func = _cb if callable(_cb) else create_booking