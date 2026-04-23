from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.customer import Customer
from app.models.enums import ChatRole


async def get_or_create_customer(
    session: AsyncSession,
    tenant_id: UUID,
    phone_number: str,
) -> Customer:
    normalized_phone = phone_number.strip()
    customer = await session.scalar(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.phone_number == normalized_phone,
        )
    )

    if customer is not None:
        return customer

    customer = Customer(
        tenant_id=tenant_id,
        phone_number=normalized_phone,
    )
    session.add(customer)
    await session.flush()
    return customer


async def get_recent_history(
    session: AsyncSession,
    customer_id: UUID,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.customer_id == customer_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    recent_desc = list(rows)
    recent_desc.reverse()

    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in recent_desc
    ]


def _normalize_role(role: str | ChatRole) -> ChatRole:
    if isinstance(role, ChatRole):
        return role
    normalized = role.strip().lower()
    if normalized == ChatRole.USER.value:
        return ChatRole.USER
    if normalized == ChatRole.ASSISTANT.value:
        return ChatRole.ASSISTANT
    raise ValueError(f"Invalid chat role: {role}")


async def save_message(
    session: AsyncSession,
    customer_id: UUID,
    role: str | ChatRole,
    content: str,
) -> ChatMessage:
    customer = await session.scalar(select(Customer).where(Customer.id == customer_id))
    if customer is None:
        raise ValueError("Customer not found")

    message = ChatMessage(
        tenant_id=customer.tenant_id,
        customer_id=customer_id,
        role=_normalize_role(role),
        content=content,
    )
    session.add(message)
    await session.flush()
    return message
