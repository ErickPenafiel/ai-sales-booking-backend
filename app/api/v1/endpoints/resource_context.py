"""
Endpoint to upload contextual resources for agents and index them into Qdrant.
Supports PDFs, images, videos and generic docs. Stores file in `media/`, registers in DB
and upserts a Qdrant point using inference embedding if available.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4, UUID
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Form
from sqlalchemy.ext.asyncio import AsyncSession

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.db.session import get_db
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "media")).absolute()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "tenant_knowledge")
QDRANT_EMBEDDING_MODEL = os.getenv("QDRANT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


@router.post("/tenants/{tenant_id}/resources/{resource_id}/context", status_code=201)
async def upload_resource_context(
    tenant_id: UUID,
    resource_id: UUID,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # persist file to disk
    ext = Path(file.filename).suffix
    filename = f"{uuid4().hex}{ext}"
    dest = MEDIA_DIR / filename
    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from exc

    # create media record in DB
    media = await crud_service.create_media(
        db, tenant_id=tenant_id, filename=file.filename, path=str(dest), content_type=file.content_type, description=description
    )

    # upsert to Qdrant using inference model if available
    q = AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), api_key=os.getenv("QDRANT_API_KEY"))

    # ensure collection exists (best effort)
    try:
        await q.get_collection(collection_name=QDRANT_COLLECTION)
    except Exception:
        try:
            await q.recreate_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=qmodels.VectorParams(size=int(os.getenv("QDRANT_VECTOR_SIZE", "1536")), distance=qmodels.Distance.COSINE),
            )
        except Exception:
            pass

    # create a qdrant Document to request inference-based embedding (if server supports it)
    doc = qmodels.Document(text=description or file.filename, model=QDRANT_EMBEDDING_MODEL)
    point = qmodels.PointStruct(id=uuid4().hex, vector=doc, payload={
        "tenant_id": str(tenant_id),
        "resource_id": str(resource_id),
        "media_id": str(media.id),
        "filename": file.filename,
        "content_type": file.content_type,
        "description": description,
    })

    try:
        await q.upsert(collection_name=QDRANT_COLLECTION, points=[point])
    except Exception as exc:
        # best-effort: don't fail the whole request if qdrant upsert fails
        # log and continue
        try:
            # fallback: use a dense placeholder vector
            size = int(os.getenv("QDRANT_VECTOR_SIZE", "1536"))
            fallback_vec = [0.0] * size
            fallback_point = qmodels.PointStruct(id=uuid4().hex, vector=fallback_vec, payload=point.payload)
            await q.upsert(collection_name=QDRANT_COLLECTION, points=[fallback_point])
        except Exception:
            pass

    return model_to_dict(media)
