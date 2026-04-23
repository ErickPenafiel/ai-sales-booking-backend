from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging
import os

from app.schemas.ai import AIRequest, AIResponse
from app.services.ai_engine import AIOrchestrator, AIEngineConfig
from app.db.session import get_db
from app.services.chat_memory_service import get_or_create_customer, get_recent_history, save_message

router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger(__name__)
_orchestrator: AIOrchestrator | None = None


def _get_orchestrator() -> AIOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator(AIEngineConfig())
    return _orchestrator


@router.post("/reply", response_model=AIResponse)
async def ai_reply(payload: AIRequest, db: AsyncSession = Depends(get_db)) -> AIResponse:
    """Tenant-scoped AI reply endpoint.

    The endpoint enforces tenant isolation and returns a strict JSON contract.
    """
    orchestrator = _get_orchestrator()
    try:
        customer = await get_or_create_customer(
            session=db,
            tenant_id=payload.tenant_id,
            phone_number=payload.customer_phone,
        )

        await save_message(
            session=db,
            customer_id=customer.id,
            role="user",
            content=payload.message,
        )

        chat_history = await get_recent_history(
            session=db,
            customer_id=customer.id,
            limit=int(os.getenv("CHAT_HISTORY_LIMIT", "3")),
        )

        result = await orchestrator.answer_customer(
            tenant_id=payload.tenant_id,
            user_message=payload.message,
            customer_phone=payload.customer_phone,
            chat_history=chat_history,
        )

        await save_message(
            session=db,
            customer_id=customer.id,
            role="assistant",
            content=result.get("answer", ""),
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI subsystem failure") from exc

    # Validate minimal contract
    if not isinstance(result, dict) or "answer" not in result or "intent" not in result:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid AI response")

    logger.info("Endpoint response: tenant=%s response=%s", payload.tenant_id, result)

    return AIResponse(
        answer=result.get("answer", ""),
        intent=result.get("intent", "INFO"),
        extracted_entities=result.get(
            "extracted_entities",
            {
                "resource_id": None,
                "date": None,
                "time": None,
                "customer_name": None,
                "customer_ci": None,
            },
        ),
    )
