"""
CRUD endpoints for Tenant Providers.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: str = Field(..., min_length=1, max_length=60)
    config: dict | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    config: dict | None = None


@router.post("/tenants/{tenant_id}/providers", status_code=201)
async def create_provider(
    tenant_id: UUID, data: ProviderCreate, db: AsyncSession = Depends(get_db)
):
    try:
        provider = await crud_service.create_provider(
            db, tenant_id=tenant_id, name=data.name, kind=data.kind, config=data.config
        )
        return model_to_dict(provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: UUID, db: AsyncSession = Depends(get_db)):
    provider = await crud_service.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return model_to_dict(provider)


@router.get("/tenants/{tenant_id}/providers")
async def list_providers(
    tenant_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    providers = await crud_service.list_providers(db, tenant_id=tenant_id)
    return [model_to_dict(p) for p in providers]


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: UUID, data: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    provider = await crud_service.update_provider(db, provider_id, **data.model_dump(exclude_unset=True))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return model_to_dict(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud_service.delete_provider(db, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
