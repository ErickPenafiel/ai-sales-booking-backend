"""
Add a third doctor to Clinica Dental Sucre for better multi-resource testing.
"""

import asyncio
import sys
from datetime import time
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.db.session import SessionLocal
from app.models.resource import Resource
from app.models.service import Service
from app.models.availability import Availability


async def add_third_doctor():
    """Add Dr. Martínez to Clinica Dental Sucre."""
    
    tenant_id = UUID("f0a6ad3c-b2c1-499e-8082-c6371940845e")
    
    async with SessionLocal() as session:
        try:
            # Create Dr. Martínez
            doctor_martinez = Resource(
                tenant_id=tenant_id,
                name="Dr. Martínez",
                kind="doctor",
                resource_metadata={"specialty": "Endodoncia", "timezone": "America/La_Paz"},
            )
            session.add(doctor_martinez)
            await session.flush()
            print(f"✓ Created resource: Dr. Martínez (ID: {doctor_martinez.id})")
            
            # Create services
            services = [
                Service(
                    tenant_id=tenant_id,
                    resource_id=doctor_martinez.id,
                    name="Consulta",
                    description="Consulta de Endodoncia",
                    duration_minutes=60,
                    price_amount=0.00,
                    currency="USD",
                ),
                Service(
                    tenant_id=tenant_id,
                    resource_id=doctor_martinez.id,
                    name="Tratamiento de Conducto",
                    description="Tratamiento de conducto radicular",
                    duration_minutes=120,
                    price_amount=0.00,
                    currency="USD",
                ),
            ]
            for service in services:
                session.add(service)
            await session.flush()
            print(f"  ✓ Created {len(services)} services")
            
            # Create availability (different schedule - only Tue, Wed, Thu full day, Fri morning)
            availability_windows = [
                # Tuesday, Wednesday, Thursday: 8:00 - 16:00
                {"day": 1, "start": time(8, 0), "end": time(16, 0)},
                {"day": 2, "start": time(8, 0), "end": time(16, 0)},
                {"day": 3, "start": time(8, 0), "end": time(16, 0)},
                # Friday: 8:00 - 12:00
                {"day": 4, "start": time(8, 0), "end": time(12, 0)},
                # Saturday: 9:00 - 13:00
                {"day": 5, "start": time(9, 0), "end": time(13, 0)},
            ]
            
            for avail_data in availability_windows:
                availability = Availability(
                    tenant_id=tenant_id,
                    resource_id=doctor_martinez.id,
                    day_of_week=avail_data["day"],
                    start_time=avail_data["start"],
                    end_time=avail_data["end"],
                    is_active=True,
                )
                session.add(availability)
            
            print(f"  ✓ Created {len(availability_windows)} availability windows")
            
            await session.commit()
            print("\n✅ Dr. Martínez successfully added to Clinica Dental Sucre!")
            print("\nNow you have 3 doctors:")
            print("  1. Dr. Penafiel - Mon-Fri (8:00-12:00, 14:00-18:00)")
            print("  2. Dra. Yrene - Mon-Fri (8:00-12:00, 14:00-18:00)")
            print("  3. Dr. Martínez - Tue-Fri, Sat (different schedule)")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Failed to add doctor: {e}")
            raise


async def main():
    await add_third_doctor()


if __name__ == "__main__":
    asyncio.run(main())
