"""
Seeder script to populate availability slots for testing the multi-resource booking flow.
Creates multiple tenants, resources (doctors), services, and availability windows.
"""

import asyncio
import logging
import sys
from datetime import time
from uuid import UUID, uuid4

from sqlalchemy import select

# Add project root to path
sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.resource import Resource
from app.models.service import Service
from app.models.availability import Availability

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def seed_availability_data():
    """Create comprehensive test data for multi-resource booking flow."""
    
    async with SessionLocal() as session:
        try:
            # Check existing data
            result = await session.execute(select(Tenant))
            existing_tenants = result.scalars().all()
            logger.info(f"Found {len(existing_tenants)} existing tenants")
            
            # Define test data structure
            tenants_data = [
                {
                    "tenant_id": UUID("f0a6ad3c-b2c1-499e-8082-c6371940845e"),  # From user example
                    "name": "Clinica Dental Sucre",
                    "slug": "clinica-dental-sucre",
                    "contact_email": "contacto@clinicasucre.com",
                    "resources": [
                        {
                            "name": "Dr. Penafiel",
                            "kind": "doctor",
                            "metadata": {"specialty": "Odontología General"},
                            "services": [
                                {"name": "Consulta General", "duration": 30, "price": 50.00},
                                {"name": "Limpieza Dental", "duration": 60, "price": 80.00},
                            ],
                            "availability": [
                                # Monday to Friday: Morning shift
                                {"day": 0, "start": time(8, 0), "end": time(12, 0)},
                                {"day": 1, "start": time(8, 0), "end": time(12, 0)},
                                {"day": 2, "start": time(8, 0), "end": time(12, 0)},
                                {"day": 3, "start": time(8, 0), "end": time(12, 0)},
                                {"day": 4, "start": time(8, 0), "end": time(12, 0)},
                                # Monday to Friday: Afternoon shift
                                {"day": 0, "start": time(14, 0), "end": time(18, 0)},
                                {"day": 1, "start": time(14, 0), "end": time(18, 0)},
                                {"day": 2, "start": time(14, 0), "end": time(18, 0)},
                                {"day": 3, "start": time(14, 0), "end": time(18, 0)},
                                {"day": 4, "start": time(14, 0), "end": time(18, 0)},
                                # Saturday: Morning only
                                {"day": 5, "start": time(9, 0), "end": time(13, 0)},
                            ],
                        },
                        {
                            "name": "Dra. López",
                            "kind": "doctor",
                            "metadata": {"specialty": "Ortodoncia"},
                            "services": [
                                {"name": "Consulta Ortodoncia", "duration": 45, "price": 70.00},
                                {"name": "Aparatos", "duration": 90, "price": 150.00},
                            ],
                            "availability": [
                                # Monday to Friday: Different schedule
                                {"day": 0, "start": time(9, 0), "end": time(13, 0)},
                                {"day": 1, "start": time(9, 0), "end": time(13, 0)},
                                {"day": 2, "start": time(9, 0), "end": time(13, 0)},
                                {"day": 3, "start": time(9, 0), "end": time(13, 0)},
                                {"day": 4, "start": time(9, 0), "end": time(13, 0)},
                                # Afternoon
                                {"day": 0, "start": time(15, 0), "end": time(19, 0)},
                                {"day": 2, "start": time(15, 0), "end": time(19, 0)},
                                {"day": 4, "start": time(15, 0), "end": time(19, 0)},
                            ],
                        },
                        {
                            "name": "Dr. Martínez",
                            "kind": "doctor",
                            "metadata": {"specialty": "Endodoncia"},
                            "services": [
                                {"name": "Consulta Endodoncia", "duration": 60, "price": 100.00},
                                {"name": "Tratamiento de Conducto", "duration": 120, "price": 200.00},
                            ],
                            "availability": [
                                # Tuesday, Wednesday, Thursday: Full day
                                {"day": 1, "start": time(8, 0), "end": time(16, 0)},
                                {"day": 2, "start": time(8, 0), "end": time(16, 0)},
                                {"day": 3, "start": time(8, 0), "end": time(16, 0)},
                                # Friday: Morning only
                                {"day": 4, "start": time(8, 0), "end": time(12, 0)},
                            ],
                        },
                    ],
                },
                {
                    "tenant_id": uuid4(),
                    "name": "Centro Médico del Valle",
                    "slug": "centro-medico-valle",
                    "contact_email": "info@centromedicovalle.com",
                    "resources": [
                        {
                            "name": "Dra. García",
                            "kind": "doctor",
                            "metadata": {"specialty": "Dermatología"},
                            "services": [
                                {"name": "Consulta Dermatológica", "duration": 30, "price": 60.00},
                            ],
                            "availability": [
                                # Monday to Friday: Extended hours to ensure future slots
                                {"day": 0, "start": time(8, 0), "end": time(18, 0)},
                                {"day": 1, "start": time(8, 0), "end": time(18, 0)},
                                {"day": 2, "start": time(8, 0), "end": time(18, 0)},
                                {"day": 3, "start": time(8, 0), "end": time(18, 0)},
                                {"day": 4, "start": time(8, 0), "end": time(18, 0)},
                                # Saturday: Morning
                                {"day": 5, "start": time(9, 0), "end": time(14, 0)},
                            ],
                        },
                        {
                            "name": "Dr. Rodríguez",
                            "kind": "doctor",
                            "metadata": {"specialty": "Cardiología"},
                            "services": [
                                {"name": "Consulta Cardiológica", "duration": 45, "price": 90.00},
                            ],
                            "availability": [
                                # Monday, Wednesday, Friday: Extended hours
                                {"day": 0, "start": time(8, 0), "end": time(17, 0)},
                                {"day": 2, "start": time(8, 0), "end": time(17, 0)},
                                {"day": 4, "start": time(8, 0), "end": time(17, 0)},
                                # Saturday: Morning
                                {"day": 5, "start": time(9, 0), "end": time(13, 0)},
                            ],
                        },
                    ],
                },
            ]
            
            created_count = {"tenants": 0, "resources": 0, "services": 0, "availabilities": 0}
            
            for tenant_data in tenants_data:
                tenant_id = tenant_data["tenant_id"]
                
                # Check if tenant already exists
                existing = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
                tenant = existing.scalar_one_or_none()
                
                if tenant:
                    logger.info(f"Tenant '{tenant.name}' already exists, skipping...")
                    continue
                
                # Create tenant
                tenant = Tenant(
                    tenant_id=tenant_id,
                    name=tenant_data["name"],
                    slug=tenant_data["slug"],
                    contact_email=tenant_data["contact_email"],
                )
                session.add(tenant)
                await session.flush()
                created_count["tenants"] += 1
                logger.info(f"✓ Created tenant: {tenant.name} (ID: {tenant.tenant_id})")
                
                # Create resources for this tenant
                for resource_data in tenant_data["resources"]:
                    resource = Resource(
                        tenant_id=tenant.tenant_id,
                        name=resource_data["name"],
                        kind=resource_data["kind"],
                        resource_metadata=resource_data.get("metadata", {}),
                    )
                    session.add(resource)
                    await session.flush()
                    created_count["resources"] += 1
                    logger.info(f"  ✓ Created resource: {resource.name}")
                    
                    # Create services for this resource
                    for service_data in resource_data["services"]:
                        service = Service(
                            tenant_id=tenant.tenant_id,
                            resource_id=resource.id,
                            name=service_data["name"],
                            description=f"Servicio de {service_data['name']}",
                            duration_minutes=service_data["duration"],
                            price_amount=service_data["price"],
                            currency="USD",
                        )
                        session.add(service)
                        await session.flush()
                        created_count["services"] += 1
                    logger.info(f"    ✓ Created {len(resource_data['services'])} services")
                    
                    # Create availability windows for this resource
                    for avail_data in resource_data["availability"]:
                        availability = Availability(
                            tenant_id=tenant.tenant_id,
                            resource_id=resource.id,
                            day_of_week=avail_data["day"],
                            start_time=avail_data["start"],
                            end_time=avail_data["end"],
                            is_active=True,
                        )
                        session.add(availability)
                        created_count["availabilities"] += 1
                    logger.info(f"    ✓ Created {len(resource_data['availability'])} availability windows")
                
            # Commit all changes
            await session.commit()
            
            # Print summary
            logger.info("\n" + "="*80)
            logger.info("SEEDING SUMMARY")
            logger.info("="*80)
            logger.info(f"Tenants created:      {created_count['tenants']}")
            logger.info(f"Resources created:    {created_count['resources']}")
            logger.info(f"Services created:     {created_count['services']}")
            logger.info(f"Availability windows: {created_count['availabilities']}")
            logger.info("="*80)
            
            if created_count["tenants"] == 0:
                logger.info("\nNo new data created. Tenants already exist in database.")
                logger.info("To reseed, delete existing tenants first or modify the tenant IDs.")
            else:
                logger.info("\n✓ Seeding completed successfully!")
                logger.info("\nYou can now test the booking flow with:")
                logger.info('  Message: "Quisiera saber si tiene horarios disponibles"')
                logger.info("  The bot should now show availability from ALL doctors.\n")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Seeding failed: {e}", exc_info=True)
            raise


async def main():
    """Main entry point."""
    logger.info("Starting availability data seeder...")
    await seed_availability_data()


if __name__ == "__main__":
    asyncio.run(main())
