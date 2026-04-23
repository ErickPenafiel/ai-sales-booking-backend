from __future__ import annotations

import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4

from app.db.session import get_db
from app.models.media import Media

router = APIRouter(prefix="/media", tags=["media"])

MEDIA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "media"))
os.makedirs(MEDIA_DIR, exist_ok=True)


@router.post("/upload")
async def upload_media(
    tenant_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # save to disk
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid4().hex}{ext}"
    dest_path = os.path.abspath(os.path.join(MEDIA_DIR, filename))

    try:
        with open(dest_path, "wb") as out_f:
            content = await file.read()
            out_f.write(content)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist file") from exc

    media = Media(
        tenant_id=tenant_id,
        filename=file.filename,
        content_type=file.content_type,
        path=dest_path,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return {"id": str(media.id), "url": f"/media/files/{filename}", "filename": media.filename}


@router.get("/files/{filename}")
async def serve_file(filename: str):
    path = os.path.abspath(os.path.join(MEDIA_DIR, filename))
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return {
        "path": path,
    }
