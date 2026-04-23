from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class WhatsAppMessagePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(validation_alias="sessionId")
    from_field: str = Field(validation_alias="from")
    text: str
    message_type: str | None = Field(default=None, validation_alias="messageType")
    has_media: bool | None = Field(default=None, validation_alias="hasMedia")
    caption: str | None = None
    mime_type: str | None = Field(default=None, validation_alias="mimeType")
    file_name: str | None = Field(default=None, validation_alias="fileName")
    media: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    message_id: str | None = Field(default=None, validation_alias="messageId")
    timestamp: int | None = None
    push_name: str | None = Field(default=None, validation_alias="pushName")


class WhatsAppSessionCreate(BaseModel):
    tenant_id: UUID


class WhatsAppSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    tenant_id: UUID
    webhook_key: str
    enabled: bool