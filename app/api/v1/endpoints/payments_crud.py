"""
CRUD API endpoints for Payments.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import PaymentStatus
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse datetime string and convert to naive (no timezone) for PostgreSQL."""
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

router = APIRouter()


class PaymentCreate(BaseModel):
    appointment_id: UUID
    provider: str = Field("mock", max_length=30)
    external_intent_id: str = Field(..., max_length=120)
    payment_link: str = Field(..., max_length=600)
    amount: float
    currency: str = Field("USD", min_length=3, max_length=3)
    status: PaymentStatus = PaymentStatus.PENDING
    provider_payload: dict | None = None


@router.post("/tenants/{tenant_id}/payments", status_code=201)
async def create_payment(
    tenant_id: UUID, data: PaymentCreate, db: AsyncSession = Depends(get_db)
):
    try:
        payment = await crud_service.create_payment(
            db,
            tenant_id=tenant_id,
            appointment_id=data.appointment_id,
            provider=data.provider,
            external_intent_id=data.external_intent_id,
            payment_link=data.payment_link,
            amount=data.amount,
            currency=data.currency,
            status=data.status,
            provider_payload=data.provider_payload,
        )
        return model_to_dict(payment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payments/{payment_id}")
async def get_payment(payment_id: UUID, db: AsyncSession = Depends(get_db)):
    payment = await crud_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return model_to_dict(payment)


@router.get("/tenants/{tenant_id}/payments")
async def list_payments(
    tenant_id: UUID,
    appointment_id: UUID | None = Query(None),
    status: PaymentStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    payments = await crud_service.list_payments(
        db,
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return [model_to_dict(p) for p in payments]


@router.put("/payments/{payment_id}/status")
async def update_payment_status(
    payment_id: UUID,
    status: PaymentStatus,
    paid_at: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    paid_at_dt = _parse_datetime(paid_at) if paid_at else None
    payment = await crud_service.update_payment_status(
        db, payment_id, status=status, paid_at=paid_at_dt
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return model_to_dict(payment)


@router.delete("/payments/{payment_id}", status_code=204)
async def delete_payment(payment_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud_service.delete_payment(db, payment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Payment not found")
