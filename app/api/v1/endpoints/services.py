"""
CRUD API endpoints for Services.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


class ServiceCreate(BaseModel):
    provider_id: UUID
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)
    duration_minutes: int = Field(..., gt=0)
    price_amount: float = Field(0.0, ge=0)
    currency: str = Field("USD", min_length=3, max_length=3)


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = Field(None, gt=0)
    price_amount: float | None = Field(None, ge=0)
    currency: str | None = None


@router.post("/tenants/{tenant_id}/services", status_code=201)
async def create_service(
    tenant_id: UUID, data: ServiceCreate, db: AsyncSession = Depends(get_db)
):
    try:
        service = await crud_service.create_service(
            db,
            tenant_id=tenant_id,
            provider_id=data.provider_id,
            name=data.name,
            description=data.description,
            duration_minutes=data.duration_minutes,
            price_amount=data.price_amount,
            currency=data.currency,
        )
        return model_to_dict(service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/services/{service_id}")
async def get_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    service = await crud_service.get_service(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return model_to_dict(service)


@router.get("/tenants/{tenant_id}/services")
async def list_services(
    tenant_id: UUID,
    provider_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    services = await crud_service.list_services(
        db, tenant_id=tenant_id, provider_id=provider_id, skip=skip, limit=limit
    )
    return [model_to_dict(s) for s in services]


@router.put("/services/{service_id}")
async def update_service(
    service_id: UUID, data: ServiceUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        service = await crud_service.update_service(
            db, service_id, **data.model_dump(exclude_unset=True)
        )
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        return model_to_dict(service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/services/{service_id}", status_code=204)
async def delete_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        deleted = await crud_service.delete_service(db, service_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Service not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
