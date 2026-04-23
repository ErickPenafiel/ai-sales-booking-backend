"""
Fix availability for Centro Médico del Valle to ensure there are slots in the next 3 days.
Since today is Friday April 10, 2026 at ~19:17 UTC, we need to add:
- Saturday April 11 (full day)
- Also ensure the existing Friday availability has future slots (it doesn't since it's past)
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


async def fix_centro_medico_availability():
    """Add more availability windows for Centro Médico del Valle."""
    
    tenant_id = UUID("19431760-6b0c-4e46-8927-4923add3a2f0")
    
    async with SessionLocal() as session:
        try:
            # Get resources
            result = await session.execute(
                select(Resource).where(Resource.tenant_id == tenant_id).order_by(Resource.name)
            )
            resources = result.scalars().all()
            
            print(f"Found {len(resources)} resources for Centro Médico del Valle:\n")
            
            added_count = 0
            
            for resource in resources:
                print(f"Processing: {resource.name}")
                
                # Add Saturday, Sunday, Monday, Tuesday, Wednesday availability
                new_availabilities = []
                
                if resource.name == "Dra. García":
                    # Add weekend and early next week
                    new_availabilities = [
                        {"day": 5, "start": time(9, 0), "end": time(18, 0)},  # Saturday
                        {"day": 6, "start": time(9, 0), "end": time(15, 0)},  # Sunday
                        {"day": 0, "start": time(8, 0), "end": time(18, 0)},  # Monday
                        {"day": 1, "start": time(8, 0), "end": time(18, 0)},  # Tuesday
                        {"day": 2, "start": time(8, 0), "end": time(18, 0)},  # Wednesday
                    ]
                elif resource.name == "Dr. Rodríguez":
                    # Add weekend and early next week
                    new_availabilities = [
                        {"day": 5, "start": time(9, 0), "end": time(15, 0)},  # Saturday
                        {"day": 6, "start": time(9, 0), "end": time(13, 0)},  # Sunday
                        {"day": 0, "start": time(8, 0), "end": time(17, 0)},  # Monday
                        {"day": 2, "start": time(8, 0), "end": time(17, 0)},  # Wednesday
                        {"day": 3, "start": time(8, 0), "end": time(17, 0)},  # Thursday
                    ]
                
                for avail_data in new_availabilities:
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
                    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                    print(f"  ✓ Added {day_names[avail_data['day']]}: {avail_data['start']} - {avail_data['end']}")
            
            await session.commit()
            
            print(f"\n{'='*80}")
            print(f"✓ Successfully added {added_count} availability windows")
            print(f"  Centro Médico del Valle now has coverage for the next 3+ days")
            print(f"{'='*80}")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Failed: {e}")
            raise


async def main():
    await fix_centro_medico_availability()


if __name__ == "__main__":
    asyncio.run(main())
