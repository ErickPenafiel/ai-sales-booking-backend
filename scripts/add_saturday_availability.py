"""
Add Saturday availability for Clinica Dental Sucre doctors.
Since today is Friday evening, we need Saturday slots for proper testing.
"""

import asyncio
import sys
from datetime import time
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.resource import Resource
from app.models.availability import Availability


async def add_saturday_availability():
    """Add Saturday availability for Clinica Dental Sucre doctors."""
    
    tenant_id = UUID("f0a6ad3c-b2c1-499e-8082-c6371940845e")
    
    async with SessionLocal() as session:
        try:
            # Get resources
            result = await session.execute(
                select(Resource).where(Resource.tenant_id == tenant_id).order_by(Resource.name)
            )
            resources = result.scalars().all()
            
            print(f"Found {len(resources)} resources for Clinica Dental Sucre:\n")
            
            added_count = 0
            
            for resource in resources:
                print(f"Processing: {resource.name}")
                
                # Add Saturday availability (day 5)
                # Check if already has Saturday availability
                result = await session.execute(
                    select(Availability).where(
                        Availability.resource_id == resource.id,
                        Availability.day_of_week == 5,  # Saturday
                        Availability.is_active == True
                    )
                )
                existing_saturday = result.scalars().all()
                
                if existing_saturday:
                    print(f"  → Already has Saturday availability, skipping")
                    continue
                
                # Add Saturday morning and afternoon
                saturday_availabilities = [
                    {"day": 5, "start": time(9, 0), "end": time(13, 0)},
                ]
                
                for avail_data in saturday_availabilities:
                    availability = Availability(
                        tenant_id=tenant_id,
                        resource_id=resource.id,
                        day_of_week=avail_data["day"],
                        start_time=avail_data["start"],
                        end_time=avail_data["end"],
                        is_active=True,
                    )
                    session.add(availability)
                    added_count += 1
                    print(f"  ✓ Added Saturday: {avail_data['start']} - {avail_data['end']}")
            
            if added_count > 0:
                await session.commit()
                print(f"\n{'='*80}")
                print(f"✓ Successfully added {added_count} Saturday availability windows")
                print(f"  Clinica Dental Sucre doctors now have Saturday coverage")
                print(f"{'='*80}")
            else:
                print(f"\n{'='*80}")
                print(f"ℹ All doctors already have Saturday availability")
                print(f"{'='*80}")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Failed: {e}")
            raise


async def main():
    await add_saturday_availability()


if __name__ == "__main__":
    asyncio.run(main())
