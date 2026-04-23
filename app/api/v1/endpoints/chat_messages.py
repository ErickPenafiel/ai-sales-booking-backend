"""
CRUD API endpoints for Chat Messages.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chat_message import ChatRole
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


class ChatMessageCreate(BaseModel):
    customer_id: UUID
    role: ChatRole
    content: str = Field(..., min_length=1)


@router.post("/customers/{customer_id}/messages", status_code=201)
async def create_chat_message(
    customer_id: UUID, data: ChatMessageCreate, db: AsyncSession = Depends(get_db)
):
    customer = await crud_service.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    message = await crud_service.create_chat_message(
        db,
        tenant_id=customer.tenant_id,
        customer_id=customer_id,
        role=data.role,
        content=data.content,
    )
    return model_to_dict(message)


@router.get("/customers/{customer_id}/messages")
async def get_chat_messages(
    customer_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    messages = await crud_service.get_chat_messages(db, customer_id, limit=limit)
    return [model_to_dict(m) for m in messages]


@router.delete("/customers/{customer_id}/messages", status_code=204)
async def delete_chat_messages(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    count = await crud_service.delete_chat_messages(db, customer_id)
    return {"deleted": count}
