"""
Test name and CI extraction with various realistic patterns.
"""

import sys

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.services.ai_engine import AIOrchestrator


def test_name_extraction():
    """Test name extraction patterns."""
    
    orchestrator = AIOrchestrator()
    
    test_cases = [
        {
            "name": "Name + CI (Diana Rodriguez mi ci es...)",
            "message": "Diana Rodriguez mi ci es 5485217123",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Name + CI (comma separated)",
            "message": "Diana Rodriguez, ci 5485217123",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Explicit name indicator",
            "message": "mi nombre es Diana Rodriguez y mi ci es 5485217123",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Me llamo pattern",
            "message": "me llamo Diana Rodriguez, mi carnet es 5485217123",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Name: pattern",
            "message": "nombre: Diana Rodriguez, ci: 5485217123",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Short name + CI",
            "message": "Diana mi ci es 5485217123",
            "expected_name": "Diana",
            "expected_ci": "5485217123",
        },
        {
            "name": "CI first, then name",
            "message": "mi ci es 5485217123, soy Diana Rodriguez",
            "expected_name": "Diana Rodriguez",
            "expected_ci": "5485217123",
        },
        {
            "name": "Only CI (no name)",
            "message": "mi ci es 5485217123",
            "expected_name": None,
            "expected_ci": "5485217123",
        },
        {
            "name": "Only name (no CI)",
            "message": "mi nombre es Diana Rodriguez",
            "expected_name": "Diana Rodriguez",
            "expected_ci": None,
        },
        {
            "name": "Name at start, booking request",
            "message": "Diana Rodriguez, quiero turno con dr rodriguez manana",
            "expected_name": "Diana Rodriguez",
            "expected_ci": None,
        },
    ]
    
    print("="*100)
    print("TESTING NAME AND CI EXTRACTION PATTERNS")
    print("="*100)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*100}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'='*100}")
        print(f'\nMessage: "{test_case["message"]}"')
        
        # Extract entities using the orchestrator's method
        entities = orchestrator._extract_entities_from_message(test_case["message"])
        
        actual_name = entities.get("customer_name")
        actual_ci = entities.get("customer_ci")
        
        print(f"\nExpected: name='{test_case['expected_name']}', ci='{test_case['expected_ci']}'")
        print(f"Actual:   name='{actual_name}', ci='{actual_ci}'")
        
        # Check if match
        name_match = (actual_name == test_case['expected_name']) or (
            actual_name is None and test_case['expected_name'] is None
        )
        ci_match = (actual_ci == test_case['expected_ci']) or (
            actual_ci is None and test_case['expected_ci'] is None
        )
        
        if name_match and ci_match:
            print(f"\n✅ PASS")
            passed += 1
        else:
            print(f"\n❌ FAIL")
            failed += 1
            if not name_match:
                print(f"   ❌ Name mismatch: expected '{test_case['expected_name']}', got '{actual_name}'")
            if not ci_match:
                print(f"   ❌ CI mismatch: expected '{test_case['expected_ci']}', got '{actual_ci}'")
    
    print("\n" + "="*100)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("="*100)
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = test_name_extraction()
    sys.exit(0 if success else 1)
