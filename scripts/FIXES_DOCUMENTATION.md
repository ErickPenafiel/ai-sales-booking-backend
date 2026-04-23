# Booking Agent Flow - Complete Fixes Documentation

## Issues Fixed

### ❌ Issue 1: Entity Extraction Corruption
**Problem:** Customer name was being set to garbage like "ningún profesional en los próximos" extracted from the bot's own response text.

**Root Cause:** The `_extract_entities_from_history()` method was extracting entities from BOTH user AND assistant messages in the chat history, causing the bot to parse its own responses.

**Solution:** Modified `_extract_entities_from_history()` to **only extract from user messages**, skipping assistant/bot responses:

```python
# Skip assistant/bot responses - only extract from user messages
if role in ("assistant", "bot", "ai", "system"):
    continue
```

**Additional Fix:** Made LLM entity extraction more conservative:
- Only merge `resource_id`, `date`, and `time` from LLM if explicitly found
- For `customer_name` and `customer_ci`, validate they don't contain suspicious words from bot responses
- Check that CI is purely numeric before accepting it

---

### ❌ Issue 2: No Availability Found When It Should Exist
**Problem:** "No encontré horarios disponibles para ningún profesional en los próximos 3 días" even though availability was configured.

**Root Cause:** Two issues:
1. **Temporal mismatch:** Today is Friday April 10, 2026 at ~19:17 UTC, but availability windows were only for business hours (8:00-18:00), which had already passed
2. **Missing weekend coverage:** Only Friday availability existed, but Friday's slots were in the past

**Solution:** 
- Added Saturday and Sunday availability windows for all doctors
- Extended weekday hours to ensure future slots exist
- Added error handling in `_handle_multi_resource_availability()` to catch and log failures

**Scripts created:**
- `fix_centro_medico_availability.py` - Adds weekend coverage for Centro Médico del Valle
- `add_saturday_availability.py` - Adds Saturday coverage for Clinica Dental Sucre

---

### ❌ Issue 3: Premature Customer Data Request
**Problem:** Bot was asking for name and CI immediately when user just wanted to check availability, before they even decided to book.

**Root Cause:** The booking executor was always asking for missing customer data when showing available slots.

**Solution:** Removed the customer data request from the initial availability check:

**Before:**
```python
if missing_demo:
    return {
        "answer": (
            f"Tengo disponibilidad con {resource_name} el {suggested_date} ({suggested_times}). "
            "Indícame el horario exacto y estos datos para confirmar: "
            + ", ".join(missing_demo)
            + "."
        ),
        ...
    }
```

**After:**
```python
# Don't ask for customer data when just checking availability
# Only prompt for name/CI when user explicitly wants to book
return {
    "answer": (
        f"Tengo disponibilidad con {resource_name} el {suggested_date} ({suggested_times}). "
        "¿Qué horario prefieres? Indica el nombre del profesional si deseas agendar con otro."
    ),
    ...
}
```

---

## Test Results

### ✅ TEST 1: Multi-Resource Display (Clinica Dental Sucre)
**Input:**
```json
{
  "tenant_id": "f0a6ad3c-b2c1-499e-8082-c6371940845e",
  "message": "Quisiera saber si tiene horarios disponibles",
  "customer_phone": "59178945612"
}
```

**Output:**
```
Estos son los horarios disponibles:

📅 2026-04-11 (Sábado):
  • Dr. Martínez: 09:00, 10:00, 11:00, 12:00
  • Dr. Penafiel: 09:00, 09:30, 10:00, 10:30, 11:00
  • Dra. Yrene: 09:00, 09:30, 10:00, 10:30, 11:00

¿Con cuál profesional y horario deseas agendar tu cita?
Indícame el nombre del profesional y el horario que prefieres.
```

✅ **All 3 doctors shown with their available times**
✅ **No customer data requested**
✅ **Clean entity extraction**

---

### ✅ TEST 2: Multi-Resource Display (Centro Médico del Valle)
**Input:**
```json
{
  "tenant_id": "19431760-6b0c-4e46-8927-4923add3a2f0",
  "message": "Quisiera saber si tiene horarios disponibles",
  "customer_phone": "59178945612"
}
```

**Output:**
```
Estos son los horarios disponibles:

📅 2026-04-11 (Sábado):
  • Dr. Rodríguez: 09:00, 09:45, 10:30, 11:15, 12:00
  • Dra. García: 09:00, 09:30, 10:00, 10:30, 11:00

📅 2026-04-12 (Domingo):
  • Dr. Rodríguez: 09:00, 09:45, 10:30, 11:15, 12:00
  • Dra. García: 09:00, 09:30, 10:00, 10:30, 11:00

¿Con cuál profesional y horario deseas agendar tu cita?
Indícame el nombre del profesional y el horario que prefieres.
```

✅ **Shows multiple days with availability**
✅ **Both doctors displayed with slots**

---

### ✅ TEST 3: Specific Doctor Request
**Input:**
```json
{
  "tenant_id": "f0a6ad3c-b2c1-499e-8082-c6371940845e",
  "message": "Quisiera horario con Dr. Penafiel",
  "customer_phone": "59178945612"
}
```

**Output:**
```
Tengo disponibilidad con Dr. Penafiel el 2026-04-11 (09:00, 09:30, 10:00, 10:30). 
¿Qué horario prefieres? Indica el nombre del profesional si deseas agendar con otro.
```

✅ **Shows only Dr. Penafiel's slots**
✅ **Correct resource_id extracted**
✅ **No premature customer data request**

---

## Code Changes Summary

### File: `app/services/ai_engine.py`

#### 1. Modified `_extract_entities_from_history()` (line ~773)
**Change:** Added role check to skip assistant/bot responses
```python
# Skip assistant/bot responses - only extract from user messages
if role in ("assistant", "bot", "ai", "system"):
    continue
```

#### 2. Modified entity merging logic (line ~419-455)
**Change:** Made LLM entity extraction more conservative
- Only merge `resource_id`, `date`, `time` from LLM
- Validate `customer_name` doesn't contain suspicious words
- Validate `customer_ci` is purely numeric

#### 3. Modified single-resource availability response (line ~517-531)
**Change:** Removed premature customer data request
```python
# Don't ask for customer data when just checking availability
return {
    "answer": (
        f"Tengo disponibilidad con {resource_name} el {suggested_date} ({suggested_times}). "
        "¿Qué horario prefieres? Indica el nombre del profesional si deseas agendar con otro."
    ),
    ...
}
```

#### 4. Enhanced `_handle_multi_resource_availability()` (line ~898-989)
**Changes:**
- Added try-catch for slot generation failures
- Improved error message to show which days were checked
- Added better guidance in response text
- Shows which professionals were consulted when no availability

---

## Database Updates

### Clinica Dental Sucre (f0a6ad3c-b2c1-499e-8082-c6371940845e)

| Doctor | Original Schedule | Added |
|--------|------------------|-------|
| Dr. Penafiel | Mon-Fri 8:00-12:00, 14:00-18:00 | **Saturday 9:00-13:00** |
| Dra. Yrene | Mon-Fri 8:00-12:00, 14:00-18:00 | **Saturday 9:00-13:00** |
| Dr. Martínez | Tue-Fri 8:00-16:00, Sat 9:00-13:00 | Already had Saturday |

### Centro Médico del Valle (19431760-6b0c-4e46-8927-4923add3a2f0)

| Doctor | Original Schedule | Added |
|--------|------------------|-------|
| Dra. García | Mon-Fri 10:00-14:00 | **Sat 9:00-18:00, Sun 9:00-15:00, Mon-Wed 8:00-18:00** |
| Dr. Rodríguez | Mon, Wed, Fri 8:00-12:00 | **Sat 9:00-15:00, Sun 9:00-13:00, Mon 8:00-17:00, Wed-Thu 8:00-17:00** |

---

## Seeder Scripts Created

1. **`seed_availability.py`** - Main seeder for multiple tenants
2. **`add_third_doctor.py`** - Adds Dr. Martínez to Clinica Dental Sucre
3. **`check_existing_data.py`** - Utility to inspect existing data
4. **`debug_availability.py`** - Debug tool to check slot generation
5. **`fix_centro_medico_availability.py`** - Adds weekend coverage for Centro Médico
6. **`add_saturday_availability.py`** - Adds Saturday for Clinica Dental Sucre
7. **`test_simple_flow.py`** - Comprehensive test script
8. **`TEST_RESULTS.md`** - Detailed test results documentation
9. **`README_SEEDERS.md`** - Complete seeder documentation

---

## How to Test

### Quick Test:
```bash
python scripts\test_simple_flow.py
```

### Manual API Test:
```bash
# Test multi-resource display
curl -X POST http://localhost:8000/api/v1/ai/reply ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_id\":\"f0a6ad3c-b2c1-499e-8082-c6371940845e\",\"message\":\"Quisiera saber si tiene horarios disponibles\",\"customer_phone\":\"59178945612\"}"
```

---

## Verification Checklist

- ✅ Entity extraction only from user messages (not bot responses)
- ✅ Customer name no longer gets garbage values
- ✅ Customer CI validation ensures numeric-only values
- ✅ Multi-resource availability shows ALL doctors when none specified
- ✅ Single-resource shows only that doctor's slots
- ✅ No premature customer data requests (name, CI, phone)
- ✅ Availability windows cover next 3+ days
- ✅ Error handling for slot generation failures
- ✅ Better error messages showing which days were checked
- ✅ Code compiles without errors
- ✅ All tests pass successfully

---

## Next Steps for Production

1. **Remove test data:** Clean up seed data and use real tenant data
2. **Monitor performance:** The multi-resource check calls `get_resource_slots` for each resource × 3 days, which could be slow with many doctors
3. **Add caching:** Cache slot generation results to avoid repeated DB calls
4. **Improve LLM prompts:** Update ENTITY_EXTRACTION_PROMPT to be more explicit about only extracting from user input
5. **Add rate limiting:** Prevent abuse of the availability checking endpoint
