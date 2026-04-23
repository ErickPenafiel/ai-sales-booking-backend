from __future__ import annotations

import logging
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.whatsapp import (
    WhatsAppMessagePayload,
    WhatsAppSessionCreate,
    WhatsAppSessionResponse,
)
from app.crud import crud_whatsapp_session
from app.services.ai_engine import AIOrchestrator, AIEngineConfig
from app.services.chat_memory_service import get_or_create_customer, get_recent_history, save_message

logger = logging.getLogger(__name__)

_orchestrator: AIOrchestrator | None = None


def _get_orchestrator() -> AIOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator(AIEngineConfig())
    return _orchestrator


def create_whatsapp_router() -> APIRouter:
    router = APIRouter(tags=["WhatsApp"])

    @router.post("/webhook")
    async def receive_webhook(
        payload: WhatsAppMessagePayload,
        x_webhook_key: str = Header(..., alias="x-webhook-key"),
        db: AsyncSession = Depends(get_db),
    ):
        session = await crud_whatsapp_session.get_session_by_key(db, x_webhook_key)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook key",
            )

        logger.info(
            "WhatsApp message received | session_id=%s | from=%s | text=%s",
            payload.session_id,
            payload.from_field,
            payload.text,
        )

        logger.info(
            "[AI AGENT] Processing message for tenant_id=%s | message=%s",
            session.tenant_id,
            payload.text,
        )

        orchestrator = _get_orchestrator()

        customer = await get_or_create_customer(
            session=db,
            tenant_id=session.tenant_id,
            phone_number=payload.from_field,
        )

        await save_message(
            session=db,
            customer_id=customer.id,
            role="user",
            content=payload.text,
        )

        chat_history = await get_recent_history(
            session=db,
            customer_id=customer.id,
            limit=int(os.getenv("CHAT_HISTORY_LIMIT", "3")),
        )

        result = await orchestrator.answer_customer(
            tenant_id=session.tenant_id,
            user_message=payload.text,
            customer_phone=payload.from_field,
            chat_history=chat_history,
        )

        await save_message(
            session=db,
            customer_id=customer.id,
            role="assistant",
            content=result.get("answer", ""),
        )
        await db.commit()

        logger.info(
            "[AI AGENT] Response generated | tenant_id=%s | answer=%s | intent=%s",
            session.tenant_id,
            result.get("answer", ""),
            result.get("intent", "UNKNOWN"),
        )

        return {"status": "received", "processed": True}

    return router


def create_whatsapp_admin_router() -> APIRouter:
    router = APIRouter(tags=["WhatsApp"])

    @router.post("/tenants/{tenant_id}/whatsapp/sessions", response_model=WhatsAppSessionResponse, status_code=201)
    async def create_session(
        payload: WhatsAppSessionCreate,
        tenant_id: UUID = Path(...),
        session_id: str = ...,
        db: AsyncSession = Depends(get_db),
    ):
        if tenant_id != payload.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id in path must match tenant_id in body",
            )

        existing = await crud_whatsapp_session.get_session_by_session_id(db, session_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already registered",
            )

        whatsapp_session = await crud_whatsapp_session.create_whatsapp_session(
            db, payload.tenant_id, session_id
        )
        await db.commit()

        return WhatsAppSessionResponse(
            session_id=whatsapp_session.session_id,
            tenant_id=whatsapp_session.tenant_id,
            webhook_key=whatsapp_session.webhook_key,
            enabled=whatsapp_session.enabled,
        )

    @router.get("/tenants/{tenant_id}/whatsapp/sessions", response_model=List[WhatsAppSessionResponse])
    async def list_sessions(
        tenant_id: UUID = Path(...),
        db: AsyncSession = Depends(get_db),
    ):
        sessions = await crud_whatsapp_session.get_sessions_by_tenant(db, tenant_id)
        return [
            WhatsAppSessionResponse(
                session_id=s.session_id,
                tenant_id=s.tenant_id,
                webhook_key=s.webhook_key,
                enabled=s.enabled,
            )
            for s in sessions
        ]

    @router.delete("/tenants/{tenant_id}/whatsapp/sessions/{session_id}")
    async def delete_session(
        tenant_id: UUID = Path(...),
        session_id: str = Path(...),
        db: AsyncSession = Depends(get_db),
    ):
        deleted = await crud_whatsapp_session.delete_whatsapp_session(db, session_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        await db.commit()
        return {"status": "deleted"}

    @router.post("/tenants/{tenant_id}/whatsapp/sessions/{session_id}/regenerate-key", response_model=WhatsAppSessionResponse)
    async def regenerate_key(
        tenant_id: UUID = Path(...),
        session_id: str = Path(...),
        db: AsyncSession = Depends(get_db),
    ):
        session = await crud_whatsapp_session.regenerate_webhook_key(db, session_id)
        if session is None or session.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        await db.commit()

        return WhatsAppSessionResponse(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            webhook_key=session.webhook_key,
            enabled=session.enabled,
        )

    return router


whatsapp_router = create_whatsapp_router()
whatsapp_admin_router = create_whatsapp_admin_router()