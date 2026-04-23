"""
CRUD API endpoints for statistics.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import crud_service

router = APIRouter()


@router.get("/stats/summary")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get overall statistics."""
    return {
        "total_tenants": await crud_service.count_tenants(db),
        "total_appointments": await crud_service.count_appointments(db),
        "total_customers": await crud_service.count_customers(db),
    }


@router.get("/tenants/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get tenant-specific statistics."""
    tenant = await crud_service.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "tenant_id": str(tenant_id),
        "total_appointments": await crud_service.count_appointments(
            db, tenant_id=tenant_id
        ),
        "total_customers": await crud_service.count_customers(db, tenant_id=tenant_id),
    }
