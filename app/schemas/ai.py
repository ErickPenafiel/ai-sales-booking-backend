from __future__ import annotations

from typing import Any
from pydantic import BaseModel
from uuid import UUID


class AIRequest(BaseModel):
    tenant_id: UUID
    message: str
    customer_phone: str


class ExtractedEntities(BaseModel):
    provider_id: str | None = None
    service_id: str | None = None
    date: str | None = None
    time: str | None = None
    customer_name: str | None = None
    customer_ci: str | None = None


class AIResponse(BaseModel):
    answer: str
    intent: str
    extracted_entities: ExtractedEntities