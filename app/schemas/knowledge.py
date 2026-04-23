"""
Pydantic schemas for Knowledge Base API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AssetType


class KnowledgeTextCreate(BaseModel):
    """Schema for creating a text-based knowledge asset."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    content: str = Field(..., min_length=1)


class KnowledgeTextResponse(BaseModel):
    """Response schema for text knowledge asset."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    asset_type: AssetType
    title: str
    description: str | None
    content: str | None
    file_url: str | None
    file_name: str | None
    is_vectorized: bool
    file_size: int | None
    mime_type: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeAssetResponse(BaseModel):
    """Response schema for knowledge asset (without content)."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    asset_type: AssetType
    title: str
    description: str | None
    file_url: str | None
    file_name: str | None
    payload: dict[str, Any] | None
    is_vectorized: bool
    file_size: int | None
    mime_type: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeListResponse(BaseModel):
    """Paginated list response for knowledge assets."""

    items: list[KnowledgeAssetResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class KnowledgeSearchResponse(BaseModel):
    """Response for knowledge search results."""

    results: list[dict[str, Any]]
    query: str
    total: int


class KnowledgeUploadResponse(BaseModel):
    """Response for file upload."""

    id: UUID
    tenant_id: UUID
    asset_type: AssetType
    title: str
    description: str | None
    file_name: str | None
    file_url: str | None
    file_size: int | None
    mime_type: str | None
    is_vectorized: bool
    status: str = "pending"


class LocationPayload(BaseModel):
    """Payload schema for location assets."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = None
    city: str | None = None
    country: str | None = None


class KnowledgeLocationCreate(BaseModel):
    """Schema for creating a location knowledge asset."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = None
    city: str | None = None
    country: str | None = None


class KnowledgeLocationResponse(BaseModel):
    """Response schema for location knowledge asset."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    asset_type: AssetType
    title: str
    description: str | None
    payload: dict[str, Any] | None
    is_vectorized: bool
    created_at: datetime
    updated_at: datetime