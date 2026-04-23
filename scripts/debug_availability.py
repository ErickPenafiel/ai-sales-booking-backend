"""
Debug script to check availability for Centro Médico del Valle
"""

import asyncio
import sys
from datetime import date, timedelta
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.db.session import SessionLocal
from app.models.resource import Resource
from app.models.availability import Availability
from app.services.booking_service import BookingService


async def debug_availability():
    """Check what availability exists for Centro Médico del Valle."""
    
    tenant_id = UUID("19431760-6b0c-4e46-8927-4923add3a2f0")
    
    async with SessionLocal() as session:
        # Get resources
        from sqlalchemy import select
        result = await session.execute(
            select(Resource).where(Resource.tenant_id == tenant_id).order_by(Resource.name)
        )
        resources = result.scalars().all()
        
        print(f"Found {len(resources)} resource(s) for Centro Médico del Valle:\n")
        
        today = date.today()
        print(f"Today is: {today.isoformat()} ({['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][today.weekday()]})")
        print(f"Checking next 3 days:\n")
        
        for resource in resources:
            print(f"\n{'='*80}")
            print(f"Resource: {resource.name} (ID: {resource.id})")
            print(f"{'='*80}")
            
            # Get availability windows
            result = await session.execute(
                select(Availability)
                .where(Availability.resource_id == resource.id, Availability.is_active == True)
                .order_by(Availability.day_of_week, Availability.start_time)
            )
            availabilities = result.scalars().all()
            
            print(f"\nConfigured Availability Windows:")
            day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            for avail in availabilities:
                print(f"  {day_names[avail.day_of_week]}: {avail.start_time} - {avail.end_time}")
            
            # Check next 3 days
            print(f"\nNext 3 days availability (via BookingService):")
            bs = BookingService(session)
            
            for offset in range(3):
                check_date = today + timedelta(days=offset)
                weekday = check_date.weekday()
                
                # Check if there's availability configured for this weekday
                day_availabilities = [a for a in availabilities if a.day_of_week == weekday]
                
                if day_availabilities:
                    print(f"  ✓ {check_date.isoformat()} ({day_names[weekday]}): {len(day_availabilities)} window(s) configured")
                    
                    # Try to get actual slots
                    try:
                        slots = await bs.get_resource_slots_for_date(
                            tenant_id=tenant_id,
                            resource_id=resource.id,
                            service_id=None,
                            target_date=check_date,
                        )
                        print(f"    → Generated {len(slots)} slot(s)")
                        if slots:
                            for slot in slots[:5]:
                                print(f"      - {slot.start_at.strftime('%H:%M')} - {slot.end_at.strftime('%H:%M')}")
                            if len(slots) > 5:
                                print(f"      ... and {len(slots) - 5} more")
                    except Exception as e:
                        print(f"    ❌ Error generating slots: {e}")
                else:
                    print(f"  ✗ {check_date.isoformat()} ({day_names[weekday]}): No availability configured")


async def main():
    await debug_availability()


if __name__ == "__main__":
    asyncio.run(main())
