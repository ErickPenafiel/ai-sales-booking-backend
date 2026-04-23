"""
Script to check existing resources and availability for Clinica Dental Sucre tenant.
"""

import asyncio
import sys
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.resource import Resource
from app.models.availability import Availability
from app.models.service import Service


async def check_existing_data():
    """Check what data exists for Clinica Dental Sucre."""
    
    tenant_id = UUID("f0a6ad3c-b2c1-499e-8082-c6371940845e")
    
    async with SessionLocal() as session:
        # Check tenant
        result = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            print(f"❌ Tenant with ID {tenant_id} not found!")
            return
        
        print(f"✓ Tenant: {tenant.name}")
        print(f"  Slug: {tenant.slug}\n")
        
        # Check resources
        result = await session.execute(
            select(Resource).where(Resource.tenant_id == tenant_id).order_by(Resource.name)
        )
        resources = result.scalars().all()
        
        print(f"Found {len(resources)} resource(s):")
        for resource in resources:
            print(f"\n  📋 {resource.name} (ID: {resource.id})")
            print(f"     Kind: {resource.kind}")
            print(f"     Metadata: {resource.resource_metadata}")
            
            # Check services for this resource
            result = await session.execute(
                select(Service).where(Service.resource_id == resource.id)
            )
            services = result.scalars().all()
            print(f"     Services: {len(services)}")
            for service in services:
                print(f"       - {service.name} ({service.duration_minutes}min, ${service.price_amount})")
            
            # Check availability for this resource
            result = await session.execute(
                select(Availability)
                .where(Availability.resource_id == resource.id, Availability.is_active == True)
                .order_by(Availability.day_of_week, Availability.start_time)
            )
            availabilities = result.scalars().all()
            print(f"     Availability windows: {len(availabilities)}")
            
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            for avail in availabilities:
                print(f"       - {day_names[avail.day_of_week]}: {avail.start_time} - {avail.end_time}")
        
        print(f"\n{'='*80}")
        if len(resources) < 3:
            print(f"⚠️  Only {len(resources)} resource(s) found. Expected 3 doctors for Clinica Dental Sucre.")
            print(f"   Need to add: Dr. Penafiel, Dra. López, Dr. Martínez")
        else:
            print(f"✓ All expected resources are present!")


async def main():
    await check_existing_data()


if __name__ == "__main__":
    asyncio.run(main())
