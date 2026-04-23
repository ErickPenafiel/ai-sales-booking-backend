"""
CRUD API endpoints for Resources.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: str = Field(..., min_length=1, max_length=60)
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata")


class ResourceUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    metadata: dict[str, Any] | None = None


# ============================================================================
# HELPERS
# ============================================================================

def model_to_dict(obj) -> dict:
    """Convert SQLAlchemy model to dict."""
    result = {}
    for key in obj.__dict__:
        if key.startswith("_"):
            continue
        value = getattr(obj, key)
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif hasattr(value, "value"):
            result[key] = value.value
        else:
            result[key] = value
    return result


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/tenants/{tenant_id}/resources", status_code=201)
async def create_resource(
    tenant_id: UUID,
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new resource for a tenant."""
    try:
        resource = await crud_service.create_resource(
            db,
            tenant_id=tenant_id,
            name=data.name,
            kind=data.kind,
            metadata=data.metadata,
        )
        return model_to_dict(resource)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get resource by ID."""
    resource = await crud_service.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return model_to_dict(resource)


@router.get("/tenants/{tenant_id}/resources")
async def list_resources(
    tenant_id: UUID,
    kind: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List tenant resources with optional filters."""
    resources = await crud_service.list_resources(
        db, tenant_id=tenant_id, kind=kind, skip=skip, limit=limit
    )
    return [model_to_dict(r) for r in resources]


@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: UUID, data: ResourceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update resource fields."""
    resource = await crud_service.update_resource(
        db, resource_id, **data.model_dump(exclude_unset=True)
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return model_to_dict(resource)


@router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(resource_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete resource (CASCADE will remove services, availabilities, appointments)."""
    deleted = await crud_service.delete_resource(db, resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resource not found")
