"""
CRUD API endpoints for Tenants.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=80)
    contact_email: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not v.replace("-", "_").isalnum():
            raise ValueError("Slug must be alphanumeric with hyphens/underscores")
        return v.lower()


class TenantUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    contact_email: str | None = None


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

@router.get("/tenants", tags=["Tenants"])
async def list_tenants_redirect():
    """Redirect /tenants to /tenants/ for backwards compatibility."""
    from fastapi import RedirectResponse
    return RedirectResponse(url="/api/v1/tenants/", status_code=307)


@router.post("/", status_code=201)
async def create_tenant(data: TenantCreate, db: AsyncSession = Depends(get_db)):
    """Create a new tenant."""
    try:
        tenant = await crud_service.create_tenant(
            db,
            name=data.name,
            slug=data.slug,
            contact_email=data.contact_email,
        )
        return model_to_dict(tenant)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenants/", tags=["Tenants"])
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all tenants with pagination."""
    tenants = await crud_service.list_tenants(db, skip=skip, limit=limit)
    return [model_to_dict(t) for t in tenants]


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get tenant by ID."""
    tenant = await crud_service.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return model_to_dict(tenant)


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: UUID, data: TenantUpdate, db: AsyncSession = Depends(get_db)
):
    """Update tenant fields."""
    tenant = await crud_service.update_tenant(
        db, tenant_id, **data.model_dump(exclude_unset=True)
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return model_to_dict(tenant)


@router.delete("/tenants/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete tenant and all related resources (CASCADE)."""
    deleted = await crud_service.delete_tenant(db, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
