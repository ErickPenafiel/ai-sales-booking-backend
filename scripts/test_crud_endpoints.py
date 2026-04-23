"""
Comprehensive test suite for all CRUD endpoints.
Tests all endpoints with valid and invalid data.
"""

import asyncio
import json
import sys
from datetime import datetime, time
from uuid import uuid4

import httpx

BASE_URL = "http://127.0.0.1:8010/api/v1"

# Test results tracking
test_results = {"passed": 0, "failed": 0, "errors": []}


def track_result(test_name: str, success: bool, detail: str = ""):
    """Track test result."""
    if success:
        test_results["passed"] += 1
        print(f"  ✅ {test_name}")
    else:
        test_results["failed"] += 1
        test_results["errors"].append(f"{test_name}: {detail}")
        print(f"  ❌ {test_name}: {detail}")


async def test_tenants(client: httpx.AsyncClient):
    """Test all tenant endpoints."""
    print("\n" + "="*80)
    print("TESTING: Tenants")
    print("="*80)

    # Test 1: Create tenant with valid data
    tenant_data = {
        "name": "Test Clinic",
        "slug": "test-clinic",
        "contact_email": "admin@testclinic.com",
    }
    response = await client.post(f"{BASE_URL}", json=tenant_data)
    track_result(
        "Create tenant (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    tenant = response.json()
    tenant_id = tenant.get("tenant_id")

    # Test 2: Create tenant with duplicate slug
    response = await client.post(f"{BASE_URL}", json=tenant_data)
    track_result(
        "Create tenant (duplicate slug)",
        response.status_code == 400,
        f"Expected 400, got {response.status_code}",
    )

    # Test 3: Create tenant with invalid slug
    invalid_slug = {"name": "Test", "slug": "test@clinic!"}
    response = await client.post(f"{BASE_URL}", json=invalid_slug)
    track_result(
        "Create tenant (invalid slug)",
        response.status_code == 422,
        f"Expected 422, got {response.status_code}",
    )

    # Test 4: Get tenant by ID
    response = await client.get(f"{BASE_URL}/{tenant_id}")
    track_result(
        "Get tenant (valid)",
        response.status_code == 200 and response.json()["name"] == "Test Clinic",
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Get non-existent tenant
    fake_id = str(uuid4())
    response = await client.get(f"{BASE_URL}/{fake_id}")
    track_result(
        "Get tenant (not found)",
        response.status_code == 404,
        f"Expected 404, got {response.status_code}",
    )

    # Test 6: Update tenant
    update_data = {"name": "Updated Clinic"}
    response = await client.put(f"{BASE_URL}/{tenant_id}", json=update_data)
    track_result(
        "Update tenant (valid)",
        response.status_code == 200 and response.json()["name"] == "Updated Clinic",
        f"Expected 200, got {response.status_code}",
    )

    # Test 7: List tenants
    response = await client.get(f"{BASE_URL}")
    track_result(
        "List tenants",
        response.status_code == 200 and isinstance(response.json(), list),
        f"Expected 200, got {response.status_code}",
    )

    # Test 8: Delete tenant
    response = await client.delete(f"{BASE_URL}/{tenant_id}")
    track_result(
        "Delete tenant (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )

    # Test 9: Delete non-existent tenant
    response = await client.delete(f"{BASE_URL}/{fake_id}")
    track_result(
        "Delete tenant (not found)",
        response.status_code == 404,
        f"Expected 404, got {response.status_code}",
    )


async def test_resources(client: httpx.AsyncClient, tenant_id: str):
    """Test all resource endpoints."""
    print("\n" + "="*80)
    print("TESTING: Resources")
    print("="*80)

    # Test 1: Create resource
    resource_data = {
        "name": "Dr. Smith",
        "kind": "doctor",
        "metadata": {"specialty": "Cardiology"},
    }
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/resources", json=resource_data
    )
    track_result(
        "Create resource (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    resource = response.json()
    resource_id = resource.get("id")

    # Test 2: Create resource for non-existent tenant
    fake_tenant = str(uuid4())
    response = await client.post(
        f"{BASE_URL}/tenants/{fake_tenant}/resources", json=resource_data
    )
    track_result(
        "Create resource (invalid tenant)",
        response.status_code == 400,
        f"Expected 400, got {response.status_code}",
    )

    # Test 3: Get resource
    response = await client.get(f"{BASE_URL}/resources/{resource_id}")
    track_result(
        "Get resource (valid)",
        response.status_code == 200 and response.json()["name"] == "Dr. Smith",
        f"Expected 200, got {response.status_code}",
    )

    # Test 4: List resources
    response = await client.get(
        f"{BASE_URL}/tenants/{tenant_id}/resources", params={"kind": "doctor"}
    )
    track_result(
        "List resources (with filter)",
        response.status_code == 200 and len(response.json()) > 0,
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Update resource
    update_data = {"name": "Dr. John Smith", "kind": "specialist"}
    response = await client.put(
        f"{BASE_URL}/resources/{resource_id}", json=update_data
    )
    track_result(
        "Update resource (valid)",
        response.status_code == 200 and response.json()["name"] == "Dr. John Smith",
        f"Expected 200, got {response.status_code}",
    )

    # Test 6: Delete resource
    response = await client.delete(f"{BASE_URL}/resources/{resource_id}")
    track_result(
        "Delete resource (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )

    return resource_id


async def test_customers(client: httpx.AsyncClient, tenant_id: str):
    """Test all customer endpoints."""
    print("\n" + "="*80)
    print("TESTING: Customers")
    print("="*80)

    # Test 1: Create customer
    customer_data = {"phone_number": "59178945612", "name": "Juan Pérez"}
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/customers", json=customer_data
    )
    track_result(
        "Create customer (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    customer = response.json()
    customer_id = customer.get("id")

    # Test 2: Create duplicate customer
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/customers", json=customer_data
    )
    track_result(
        "Create customer (duplicate phone)",
        response.status_code == 400,
        f"Expected 400, got {response.status_code}",
    )

    # Test 3: Get customer
    response = await client.get(f"{BASE_URL}/customers/{customer_id}")
    track_result(
        "Get customer (valid)",
        response.status_code == 200 and response.json()["name"] == "Juan Pérez",
        f"Expected 200, got {response.status_code}",
    )

    # Test 4: List customers
    response = await client.get(f"{BASE_URL}/tenants/{tenant_id}/customers")
    track_result(
        "List customers",
        response.status_code == 200 and isinstance(response.json(), list),
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Update customer
    update_data = {"name": "Juan Carlos Pérez"}
    response = await client.put(
        f"{BASE_URL}/customers/{customer_id}", json=update_data
    )
    track_result(
        "Update customer (valid)",
        response.status_code == 200 and response.json()["name"] == "Juan Carlos Pérez",
        f"Expected 200, got {response.status_code}",
    )

    # Test 6: Delete customer
    response = await client.delete(f"{BASE_URL}/customers/{customer_id}")
    track_result(
        "Delete customer (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )


async def test_services(client: httpx.AsyncClient, tenant_id: str, resource_id: str):
    """Test all service endpoints."""
    print("\n" + "="*80)
    print("TESTING: Services")
    print("="*80)

    # Test 1: Create service
    service_data = {
        "resource_id": resource_id,
        "name": "Consulta General",
        "duration_minutes": 30,
        "price_amount": 50.00,
        "currency": "USD",
    }
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/services", json=service_data
    )
    track_result(
        "Create service (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    service = response.json()
    service_id = service.get("id")

    # Test 2: Create service with invalid duration
    invalid_data = {**service_data, "duration_minutes": -5}
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/services", json=invalid_data
    )
    track_result(
        "Create service (invalid duration)",
        response.status_code == 422,
        f"Expected 422, got {response.status_code}",
    )

    # Test 3: Get service
    response = await client.get(f"{BASE_URL}/services/{service_id}")
    track_result(
        "Get service (valid)",
        response.status_code == 200 and response.json()["name"] == "Consulta General",
        f"Expected 200, got {response.status_code}",
    )

    # Test 4: Update service
    update_data = {"price_amount": 75.00}
    response = await client.put(
        f"{BASE_URL}/services/{service_id}", json=update_data
    )
    track_result(
        "Update service (valid)",
        response.status_code == 200 and response.json()["price_amount"] == 75.0,
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Delete service
    response = await client.delete(f"{BASE_URL}/services/{service_id}")
    track_result(
        "Delete service (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )

    return service_id


async def test_availability(client: httpx.AsyncClient, tenant_id: str, resource_id: str):
    """Test all availability endpoints."""
    print("\n" + "="*80)
    print("TESTING: Availability")
    print("="*80)

    # Test 1: Create availability
    avail_data = {
        "resource_id": resource_id,
        "day_of_week": 1,
        "start_time": "08:00:00",
        "end_time": "12:00:00",
        "is_active": True,
    }
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/availabilities", json=avail_data
    )
    track_result(
        "Create availability (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    availability = response.json()
    avail_id = availability.get("id")

    # Test 2: Create with invalid day
    invalid_data = {**avail_data, "day_of_week": 7}
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/availabilities", json=invalid_data
    )
    track_result(
        "Create availability (invalid day)",
        response.status_code == 422,
        f"Expected 422, got {response.status_code}",
    )

    # Test 3: Create with invalid time range
    invalid_time = {**avail_data, "start_time": "12:00:00", "end_time": "08:00:00"}
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/availabilities", json=invalid_time
    )
    track_result(
        "Create availability (invalid time)",
        response.status_code == 400,
        f"Expected 400, got {response.status_code}",
    )

    # Test 4: List availabilities
    response = await client.get(
        f"{BASE_URL}/tenants/{tenant_id}/availabilities",
        params={"day_of_week": 1, "is_active": True},
    )
    track_result(
        "List availabilities (with filters)",
        response.status_code == 200 and len(response.json()) > 0,
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Update availability
    update_data = {"is_active": False}
    response = await client.put(
        f"{BASE_URL}/availabilities/{avail_id}", json=update_data
    )
    track_result(
        "Update availability (valid)",
        response.status_code == 200 and response.json()["is_active"] is False,
        f"Expected 200, got {response.status_code}",
    )

    # Test 6: Delete availability
    response = await client.delete(f"{BASE_URL}/availabilities/{avail_id}")
    track_result(
        "Delete availability (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )


async def test_appointments(client: httpx.AsyncClient, tenant_id: str, resource_id: str, service_id: str):
    """Test all appointment endpoints."""
    print("\n" + "="*80)
    print("TESTING: Appointments")
    print("="*80)

    # Test 1: Create appointment
    appt_data = {
        "resource_id": resource_id,
        "service_id": service_id,
        "customer_name": "Juan Pérez",
        "customer_phone": "59178945612",
        "start_at": "2026-04-15T09:00:00",
        "end_at": "2026-04-15T09:30:00",
        "total_amount": 50.00,
        "currency": "USD",
    }
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/appointments", json=appt_data
    )
    track_result(
        "Create appointment (valid)",
        response.status_code == 201,
        f"Expected 201, got {response.status_code}",
    )
    appointment = response.json()
    appt_id = appointment.get("id")

    # Test 2: Create with invalid datetime
    invalid_data = {**appt_data, "start_at": "invalid-date"}
    response = await client.post(
        f"{BASE_URL}/tenants/{tenant_id}/appointments", json=invalid_data
    )
    track_result(
        "Create appointment (invalid datetime)",
        response.status_code == 400,
        f"Expected 400, got {response.status_code}",
    )

    # Test 3: Get appointment
    response = await client.get(f"{BASE_URL}/appointments/{appt_id}")
    track_result(
        "Get appointment (valid)",
        response.status_code == 200 and response.json()["customer_name"] == "Juan Pérez",
        f"Expected 200, got {response.status_code}",
    )

    # Test 4: List appointments
    response = await client.get(
        f"{BASE_URL}/tenants/{tenant_id}/appointments",
        params={"customer_phone": "59178945612"},
    )
    track_result(
        "List appointments (with filter)",
        response.status_code == 200 and len(response.json()) > 0,
        f"Expected 200, got {response.status_code}",
    )

    # Test 5: Cancel appointment
    response = await client.post(f"{BASE_URL}/appointments/{appt_id}/cancel")
    track_result(
        "Cancel appointment (valid)",
        response.status_code == 200 and response.json()["status"] == "CANCELLED",
        f"Expected 200, got {response.status_code}",
    )

    # Test 6: Delete appointment
    response = await client.delete(f"{BASE_URL}/appointments/{appt_id}")
    track_result(
        "Delete appointment (valid)",
        response.status_code == 204,
        f"Expected 204, got {response.status_code}",
    )


async def test_statistics(client: httpx.AsyncClient, tenant_id: str):
    """Test statistics endpoints."""
    print("\n" + "="*80)
    print("TESTING: Statistics")
    print("="*80)

    # Test 1: Get overall stats
    response = await client.get(f"{BASE_URL}/stats/summary")
    track_result(
        "Get overall stats",
        response.status_code == 200 and "total_tenants" in response.json(),
        f"Expected 200, got {response.status_code}",
    )

    # Test 2: Get tenant stats
    response = await client.get(f"{BASE_URL}/tenants/{tenant_id}/stats")
    track_result(
        "Get tenant stats",
        response.status_code == 200 and response.json()["tenant_id"] == tenant_id,
        f"Expected 200, got {response.status_code}",
    )


async def run_all_tests():
    """Run all CRUD endpoint tests."""
    print("="*80)
    print("COMPREHENSIVE CRUD ENDPOINT TESTS")
    print("="*80)

    async with httpx.AsyncClient() as client:
        # Test 1: Tenants (creates tenant for other tests)
        print("\n--- Creating tenant for tests ---")
        tenant_data = {
            "name": "Comprehensive Test Clinic",
            "slug": "comprehensive-test",
            "contact_email": "test@example.com",
        }
        response = await client.post(f"{BASE_URL}", json=tenant_data)
        if response.status_code != 201:
            print(f"❌ Failed to create test tenant: {response.text}")
            return
        tenant = response.json()
        tenant_id = tenant["tenant_id"]
        print(f"✅ Created test tenant: {tenant_id}")

        # Test 2: Resources (creates resource for other tests)
        print("\n--- Creating resource for tests ---")
        resource_data = {"name": "Dr. Test", "kind": "doctor", "metadata": {}}
        response = await client.post(
            f"{BASE_URL}/tenants/{tenant_id}/resources", json=resource_data
        )
        if response.status_code != 201:
            print(f"❌ Failed to create test resource: {response.text}")
            return
        resource = response.json()
        resource_id = resource["id"]
        print(f"✅ Created test resource: {resource_id}")

        # Test 3: Services (creates service for other tests)
        print("\n--- Creating service for tests ---")
        service_data = {
            "resource_id": resource_id,
            "name": "Test Service",
            "duration_minutes": 30,
            "price_amount": 50.0,
            "currency": "USD",
        }
        response = await client.post(
            f"{BASE_URL}/tenants/{tenant_id}/services", json=service_data
        )
        if response.status_code != 201:
            print(f"❌ Failed to create test service: {response.text}")
            return
        service = response.json()
        service_id = service["id"]
        print(f"✅ Created test service: {service_id}")

        # Run all tests
        await test_tenants(client)
        await test_resources(client, tenant_id)
        await test_customers(client, tenant_id)
        await test_services(client, tenant_id, resource_id)
        await test_availability(client, tenant_id, resource_id)
        await test_appointments(client, tenant_id, resource_id, service_id)
        await test_statistics(client, tenant_id)

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    print(f"📊 Total:  {test_results['passed'] + test_results['failed']}")

    if test_results["errors"]:
        print("\n❌ Failed Tests:")
        for error in test_results["errors"]:
            print(f"  - {error}")

    print("="*80)

    if test_results["failed"] == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {test_results['failed']} TEST(S) FAILED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
