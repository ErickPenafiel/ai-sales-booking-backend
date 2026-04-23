"""
Knowledge Base API endpoints.
"""

from __future__ import annotations

import os
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import AssetType
from app.schemas.knowledge import (
    KnowledgeAssetResponse,
    KnowledgeListResponse,
    KnowledgeSearchResponse,
    KnowledgeTextCreate,
    KnowledgeTextResponse,
    KnowledgeUploadResponse,
    LocationPayload,
)
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("/tenants/{tenant_id}/knowledge", status_code=status.HTTP_201_CREATED)
async def create_text_knowledge(
    tenant_id: UUID,
    data: KnowledgeTextCreate,
    db: AsyncSession = Depends(get_db),
) -> KnowledgeTextResponse:
    """
    Create a text-based knowledge asset.
    Input text is stored and vectorized.
    """
    asset = await knowledge_service.create_text_asset(
        session=db,
        tenant_id=tenant_id,
        title=data.title,
        description=data.description,
        content=data.content,
    )

    try:
        await knowledge_service.process_asset(db, asset.id)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to vectorize: {str(e)}",
        )

    return KnowledgeTextResponse.model_validate(asset)


@router.post("/tenants/{tenant_id}/knowledge/location", status_code=status.HTTP_201_CREATED)
async def create_location_knowledge(
    tenant_id: UUID,
    location: LocationPayload,
    title: str = Form(...),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeAssetResponse:
    """
    Create a location-based knowledge asset.
    Stores lat/lng coordinates and vectorizes title+description.
    """
    from app.models.knowledge_asset import KnowledgeAsset
    from uuid import uuid4

    asset = KnowledgeAsset(
        id=uuid4(),
        tenant_id=tenant_id,
        asset_type=AssetType.LOCATION,
        title=title,
        description=description,
        payload={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "address": location.address,
            "city": location.city,
            "country": location.country,
        },
        is_vectorized=False,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)

    try:
        await knowledge_service.process_asset(db, asset.id)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to vectorize: {str(e)}",
        )

    return KnowledgeAssetResponse.model_validate(asset)


@router.post(
    "/tenants/{tenant_id}/knowledge/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_knowledge_file(
    tenant_id: UUID,
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeUploadResponse:
    """
    Upload a file to the knowledge base.
    Supported types: PDF, TXT, Images, Audio, Video.
    Max file size: 10MB.
    """
    if file.size and file.size > knowledge_service.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {knowledge_service.MAX_FILE_SIZE} bytes (10MB)",
        )

    content = await file.read()

    if len(content) > knowledge_service.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {knowledge_service.MAX_FILE_SIZE} bytes (10MB)",
        )

    mime_type = file.content_type or "application/octet-stream"

    try:
        asset = await knowledge_service.upload_file_asset(
            session=db,
            tenant_id=tenant_id,
            file_content=content,
            file_name=file.filename or "unknown",
            mime_type=mime_type,
            title=title,
            description=description,
        )

        await db.commit()
        await db.refresh(asset)

        return KnowledgeUploadResponse(
            id=asset.id,
            tenant_id=asset.tenant_id,
            asset_type=asset.asset_type,
            title=asset.title,
            description=asset.description,
            file_name=asset.file_name,
            file_url=asset.file_url,
            file_size=asset.file_size,
            mime_type=asset.mime_type,
            is_vectorized=asset.is_vectorized,
            status="uploaded",
        )

    except knowledge_service.FileTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except knowledge_service.UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tenants/{tenant_id}/knowledge")
async def list_knowledge_assets(
    tenant_id: UUID,
    asset_type: AssetType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeListResponse:
    """
    List knowledge assets for a tenant.
    Supports filtering by asset type and pagination.
    """
    skip = (page - 1) * page_size

    assets, total = await knowledge_service.list_assets(
        session=db,
        tenant_id=tenant_id,
        asset_type=asset_type,
        skip=skip,
        limit=page_size,
    )

    return KnowledgeListResponse(
        items=[KnowledgeAssetResponse.model_validate(a) for a in assets],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(skip + len(assets)) < total,
    )


@router.get("/knowledge/{asset_id}")
async def get_knowledge_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> KnowledgeAssetResponse:
    """Get a specific knowledge asset by ID."""
    asset = await knowledge_service.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge asset not found",
        )
    return KnowledgeAssetResponse.model_validate(asset)


@router.delete("/knowledge/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_asset(
    asset_id: UUID,
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge asset and its vectors."""
    deleted = await knowledge_service.delete_asset(db, asset_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge asset not found or access denied",
        )
    await db.commit()


@router.post("/knowledge/{asset_id}/process")
async def reprocess_knowledge_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reprocess and vectorize an existing asset."""
    asset = await knowledge_service.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge asset not found",
        )

    try:
        success = await knowledge_service.process_asset(db, asset_id)
        await db.commit()
        await db.refresh(asset)

        return {
            "id": str(asset_id),
            "success": success,
            "is_vectorized": asset.is_vectorized,
            "message": "Asset reprocessed successfully" if success else "Processing failed",
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tenants/{tenant_id}/knowledge/search")
async def search_knowledge(
    tenant_id: UUID,
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeSearchResponse:
    """
    Search the knowledge base for a tenant.
    Returns relevant chunks with relevance scores.
    """
    results = await knowledge_service.search_knowledge(
        session=db,
        tenant_id=tenant_id,
        query=q,
        limit=limit,
    )

    return KnowledgeSearchResponse(
        results=results,
        query=q,
        total=len(results),
    )


@router.get("/files/{asset_id}/{filename}")
async def serve_knowledge_file(
    asset_id: UUID,
    filename: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Serve uploaded knowledge files.
    Files are stored in ./knowledge_files directory.
    """
    asset = await knowledge_service.get_asset(db, asset_id)
    if not asset or not asset.file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_path = os.path.join("./knowledge_files", str(asset_id), filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=asset.mime_type or "application/octet-stream",
    )