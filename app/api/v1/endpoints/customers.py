"""
CRUD API endpoints for Customers.
"""

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

class CustomerCreate(BaseModel):
    phone_number: str = Field(..., min_length=1, max_length=32)
    name: str | None = Field(None, max_length=120)


class CustomerUpdate(BaseModel):
    phone_number: str | None = None
    name: str | None = None


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

@router.post("/tenants/{tenant_id}/customers", status_code=201)
async def create_customer(
    tenant_id: UUID,
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer."""
    try:
        customer = await crud_service.create_customer(
            db,
            tenant_id=tenant_id,
            phone_number=data.phone_number,
            name=data.name,
        )
        return model_to_dict(customer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get customer by ID."""
    customer = await crud_service.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return model_to_dict(customer)


@router.get("/tenants/{tenant_id}/customers")
async def list_customers(
    tenant_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List tenant customers."""
    customers = await crud_service.list_customers(
        db, tenant_id=tenant_id, skip=skip, limit=limit
    )
    return [model_to_dict(c) for c in customers]


@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: UUID, data: CustomerUpdate, db: AsyncSession = Depends(get_db)
):
    """Update customer fields."""
    try:
        customer = await crud_service.update_customer(
            db, customer_id, **data.model_dump(exclude_unset=True)
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return model_to_dict(customer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/customers/{customer_id}", status_code=204)
async def delete_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete customer (CASCADE will remove chat messages)."""
    deleted = await crud_service.delete_customer(db, customer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Customer not found")
