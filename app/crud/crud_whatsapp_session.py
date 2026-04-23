from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp_session import WhatsAppSession


async def create_whatsapp_session(
    session: AsyncSession,
    tenant_id: UUID,
    session_id: str,
) -> WhatsAppSession:
    whatsapp_session = WhatsAppSession(
        session_id=session_id,
        tenant_id=tenant_id,
        webhook_key=WhatsAppSession.generate_webhook_key(),
        enabled=True,
    )
    session.add(whatsapp_session)
    await session.flush()
    return whatsapp_session


async def get_session_by_key(
    session: AsyncSession,
    webhook_key: str,
) -> WhatsAppSession | None:
    result = await session.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.webhook_key == webhook_key,
            WhatsAppSession.enabled == True,
        )
    )
    return result.scalar_one_or_none()


async def get_session_by_session_id(
    session: AsyncSession,
    session_id: str,
) -> WhatsAppSession | None:
    result = await session.execute(
        select(WhatsAppSession).where(WhatsAppSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_sessions_by_tenant(
    session: AsyncSession,
    tenant_id: UUID,
) -> List[WhatsAppSession]:
    result = await session.execute(
        select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def delete_whatsapp_session(
    session: AsyncSession,
    session_id: str,
) -> bool:
    whatsapp_session = await get_session_by_session_id(session, session_id)
    if whatsapp_session is None:
        return False
    await session.delete(whatsapp_session)
    await session.flush()
    return True


async def regenerate_webhook_key(
    session: AsyncSession,
    session_id: str,
) -> WhatsAppSession | None:
    whatsapp_session = await get_session_by_session_id(session, session_id)
    if whatsapp_session is None:
        return None
    whatsapp_session.webhook_key = WhatsAppSession.generate_webhook_key()
    await session.flush()
    return whatsapp_session