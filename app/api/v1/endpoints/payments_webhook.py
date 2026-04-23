from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, PaymentStatus
from app.models.payment import Payment
from app.schemas.payment import PaymentWebhookPayload

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def payment_webhook(payload: PaymentWebhookPayload, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    payment = await db.scalar(
        select(Payment).where(
            Payment.tenant_id == payload.tenant_id,
            Payment.external_intent_id == payload.payment_intent_id,
        )
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment intent not found")

    normalized_status = payload.status.upper()
    if normalized_status == "SUCCEEDED":
        payment.status = PaymentStatus.SUCCEEDED
        paid_at = payload.paid_at or datetime.now(timezone.utc)
        if paid_at.tzinfo is not None:
            paid_at = paid_at.astimezone(timezone.utc).replace(tzinfo=None)
        payment.paid_at = paid_at

        appointment = await db.scalar(select(Appointment).where(Appointment.id == payment.appointment_id))
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        appointment.status = AppointmentStatus.CONFIRMED
    elif normalized_status == "FAILED":
        payment.status = PaymentStatus.FAILED
    elif normalized_status == "CANCELLED":
        payment.status = PaymentStatus.CANCELLED
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported webhook status")

    payment.provider_payload = payload.raw_payload
    await db.commit()
    return {"result": "accepted"}
