"""
CRUD API endpoints for Availabilities.
"""

from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


class AvailabilityCreate(BaseModel):
    provider_id: UUID
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    is_active: bool = True


class AvailabilityUpdate(BaseModel):
    day_of_week: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None


@router.post("/tenants/{tenant_id}/availabilities", status_code=201)
async def create_availability(
    tenant_id: UUID, data: AvailabilityCreate, db: AsyncSession = Depends(get_db)
):
    try:
        availability = await crud_service.create_availability(
            db,
            tenant_id=tenant_id,
            provider_id=data.provider_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            is_active=data.is_active,
        )
        return model_to_dict(availability)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/availabilities/{availability_id}")
async def get_availability(availability_id: UUID, db: AsyncSession = Depends(get_db)):
    availability = await crud_service.get_availability(db, availability_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Availability not found")
    return model_to_dict(availability)


@router.get("/tenants/{tenant_id}/availabilities")
async def list_availabilities(
    tenant_id: UUID,
    provider_id: UUID | None = Query(None),
    day_of_week: int | None = Query(None, ge=0, le=6),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    availabilities = await crud_service.list_availabilities(
        db,
        tenant_id=tenant_id,
        provider_id=provider_id,
        day_of_week=day_of_week,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return [model_to_dict(a) for a in availabilities]


@router.put("/availabilities/{availability_id}")
async def update_availability(
    availability_id: UUID, data: AvailabilityUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        availability = await crud_service.update_availability(
            db, availability_id, **data.model_dump(exclude_unset=True)
        )
        if not availability:
            raise HTTPException(status_code=404, detail="Availability not found")
        return model_to_dict(availability)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/availabilities/{availability_id}", status_code=204)
async def delete_availability(availability_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud_service.delete_availability(db, availability_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Availability not found")
