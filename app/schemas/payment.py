from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentIntentResponse(BaseModel):
    payment_intent_id: str
    payment_link: str
    expires_at: datetime


class PaymentWebhookPayload(BaseModel):
    tenant_id: UUID
    payment_intent_id: str = Field(min_length=6, max_length=120)
    status: str
    paid_at: datetime | None = None
    raw_payload: dict[str, object] | None = None
