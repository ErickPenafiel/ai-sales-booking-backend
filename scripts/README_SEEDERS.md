# Seeder Scripts - Documentation

## Overview

These scripts help populate the database with test data for the multi-resource booking flow.

## Available Scripts

### 1. `seed_availability.py`
**Purpose:** Main seeder that creates multiple tenants with resources, services, and availability windows.

**What it creates:**
- **Clinica Dental Sucre** (if not exists)
  - 3 doctors with different schedules
  - Multiple services per doctor
  - Availability windows (Mon-Sat)
  
- **Centro Médico del Valle** (new tenant)
  - 2 doctors (Dra. García, Dr. Rodríguez)
  - Different specialties and schedules

**Usage:**
```bash
python scripts/seed_availability.py
```

**Note:** Script skips tenants that already exist (by tenant_id).

---

### 2. `add_third_doctor.py`
**Purpose:** Adds Dr. Martínez to Clinica Dental Sucre for better testing scenarios.

**What it creates:**
- Resource: Dr. Martínez (Endodoncia specialist)
- Services: Consulta (60min), Tratamiento de Conducto (120min)
- Availability: Tue-Fri 8:00-16:00, Sat 9:00-13:00

**Usage:**
```bash
python scripts/add_third_doctor.py
```

---

### 3. `check_existing_data.py`
**Purpose:** Utility script to inspect existing data for Clinica Dental Sucre.

**What it shows:**
- Tenant information
- All resources (doctors) with their details
- Services per doctor
- Availability windows per doctor

**Usage:**
```bash
python scripts/check_existing_data.py
```

---

### 4. `test_multi_resource_flow.py`
**Purpose:** Tests the new multi-resource booking flow to verify correct behavior.

**What it tests:**
1. User asks WITHOUT specifying a doctor → Should show ALL doctors
2. User asks WITH specific doctor → Should show only that doctor
3. Different doctor name variations

**Usage:**
```bash
python scripts/test_multi_resource_flow.py
```

**Expected Output:**
```
TEST 1: User asks for availability WITHOUT specifying a doctor
User message: "Quisiera saber si tiene horarios disponibles"

Intent: BOOKING_IN_PROGRESS

Bot response:
--------------------------------------------------------------------------------
Estos son los horarios disponibles:

📅 2026-04-11 (Sábado):
  • Dr. Martínez: 09:00, 10:00, 11:00, 12:00

¿Con cuál profesional y horario deseas agendar tu cita?
```

---

## Current Database State

### Clinica Dental Sucre
**Tenant ID:** `f0a6ad3c-b2c1-499e-8082-c6371940845e`

| Doctor | ID | Schedule |
|--------|-----|----------|
| Dr. Penafiel | `b8529aac-d0ea-4b2a-8cd7-47564772eea9` | Mon-Fri: 8:00-12:00, 14:00-18:00 |
| Dra. Yrene | `1ebde356-4954-40f1-803f-38539fcb9892` | Mon-Fri: 8:00-12:00, 14:00-18:00 |
| Dr. Martínez | `2f0b4691-f089-4a36-9a67-f104ff634d1e` | Tue-Fri: 8:00-16:00, Sat: 9:00-13:00 |

### Centro Médico del Valle
**Tenant ID:** `19431760-6b0c-4e46-8927-4923add3a2f0`

| Doctor | ID | Schedule |
|--------|-----|----------|
| Dra. García | (see DB) | Mon-Fri: 10:00-14:00 |
| Dr. Rodríguez | (see DB) | Mon, Wed, Fri: 8:00-12:00 |

---

## Quick Start

To set up test data from scratch:

```bash
# 1. Run main seeder (creates tenants if not exist)
python scripts/seed_availability.py

# 2. Verify data
python scripts/check_existing_data.py

# 3. Test the flow
python scripts/test_multi_resource_flow.py
```

---

## Testing the API Manually

After running the seeders, test the booking flow:

### Test 1: No doctor specified (shows ALL doctors)
```bash
curl -X POST http://localhost:8000/api/v1/ai/reply \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "f0a6ad3c-b2c1-499e-8082-c6371940845e",
    "message": "Quisiera saber si tiene horarios disponibles",
    "customer_phone": "59178945612"
  }'
```

**Expected Response:**
```json
{
  "answer": "Estos son los horarios disponibles:\n\n📅 2026-04-11 (Sábado):\n  • Dr. Martínez: 09:00, 10:00, 11:00, 12:00\n\n¿Con cuál profesional y horario deseas agendar tu cita?",
  "intent": "BOOKING_IN_PROGRESS",
  "extracted_entities": {
    "resource_id": null,
    ...
  }
}
```

### Test 2: Specific doctor (shows only that doctor)
```bash
curl -X POST http://localhost:8000/api/v1/ai/reply \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "f0a6ad3c-b2c1-499e-8082-c6371940845e",
    "message": "Quisiera saber si tiene horarios disponibles con Dr. Penafiel",
    "customer_phone": "59178945612"
  }'
```

**Expected Response:**
```json
{
  "answer": "Tengo disponibilidad con Dr. Penafiel el 2026-04-13 (08:00, 08:30, 09:00, 09:30). Indícame el horario exacto y estos datos para confirmar: nombre, CI.",
  "intent": "BOOKING_IN_PROGRESS",
  "extracted_entities": {
    "resource_id": "b8529aac-d0ea-4b2a-8cd7-47564772eea9",
    ...
  }
}
```

---

## Troubleshooting

### Issue: "Tenant already exists"
**Solution:** This is expected! The script skips existing tenants. Use `check_existing_data.py` to verify what's already there.

### Issue: "No availability found"
**Solution:** Run `add_third_doctor.py` or check if availability windows were created properly.

### Issue: "Connection refused"
**Solution:** Ensure your PostgreSQL database is running and the `.env` file has the correct `DATABASE_URL`.

---

## Code Changes Reference

See `TEST_RESULTS.md` for detailed information about the code changes made to support multi-resource booking flow.
