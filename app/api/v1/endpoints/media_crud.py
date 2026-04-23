"""
CRUD API endpoints for Media.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


class MediaCreate(BaseModel):
    filename: str = Field(..., max_length=255)
    path: str = Field(..., max_length=1024)
    content_type: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=500)


class MediaUpdate(BaseModel):
    description: str | None = None


@router.post("/tenants/{tenant_id}/media", status_code=201)
async def create_media(
    tenant_id: UUID, data: MediaCreate, db: AsyncSession = Depends(get_db)
):
    media = await crud_service.create_media(
        db,
        tenant_id=tenant_id,
        filename=data.filename,
        path=data.path,
        content_type=data.content_type,
        description=data.description,
    )
    return model_to_dict(media)


@router.get("/media/{media_id}")
async def get_media(media_id: UUID, db: AsyncSession = Depends(get_db)):
    media = await crud_service.get_media(db, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return model_to_dict(media)


@router.get("/tenants/{tenant_id}/media")
async def list_media(
    tenant_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    media_files = await crud_service.list_media(
        db, tenant_id=tenant_id, skip=skip, limit=limit
    )
    return [model_to_dict(m) for m in media_files]


@router.put("/media/{media_id}")
async def update_media(
    media_id: UUID, data: MediaUpdate, db: AsyncSession = Depends(get_db)
):
    media = await crud_service.update_media(db, media_id, description=data.description)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return model_to_dict(media)


@router.delete("/media/{media_id}", status_code=204)
async def delete_media(media_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud_service.delete_media(db, media_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media not found")
