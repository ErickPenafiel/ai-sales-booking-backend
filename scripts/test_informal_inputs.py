"""
Test booking flow with various informal user inputs.
Tests different ways users might speak: without accents, with numbers, abbreviations, etc.
"""

import asyncio
import json
import sys
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.services.ai_engine import AIOrchestrator


async def test_informal_inputs():
    """Test the booking flow with realistic informal user inputs."""
    
    orchestrator = AIOrchestrator()
    tenant_id = UUID("19431760-6b0c-4e46-8927-4923add3a2f0")
    phone = "59178945612"
    
    test_cases = [
        {
            "name": "Full formal request",
            "message": "Quisiera agendar para el dia de manana con el dr. Rodriguez a las 09:00",
            "tenant_id": tenant_id,
        },
        {
            "name": "Casual with accents missing",
            "message": "quiero turno con rodriguez manana a las 9",
            "tenant_id": tenant_id,
        },
        {
            "name": "Very informal",
            "message": "hay horario con el dr rodriguez para manana?",
            "tenant_id": tenant_id,
        },
        {
            "name": "Time without colon",
            "message": "turno con dr rodriguez manana 900",
            "tenant_id": tenant_id,
        },
        {
            "name": "No doctor specified",
            "message": "que horarios hay para manana?",
            "tenant_id": tenant_id,
        },
        {
            "name": "Just time and date",
            "message": "disponible manana 10:00?",
            "tenant_id": tenant_id,
        },
        {
            "name": "Full name with title",
            "message": "quiero cita con el Doctor Rodriguez a las 09:30",
            "tenant_id": tenant_id,
        },
    ]
    
    print("="*100)
    print("TESTING INFORMAL USER INPUTS - REALISTIC CONVERSATION PATTERNS")
    print("="*100)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*100}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'='*100}")
        print(f'\nUser message: "{test_case["message"]}"')
        print()
        
        try:
            result = await orchestrator.answer_customer(
                tenant_id=test_case["tenant_id"],
                user_message=test_case["message"],
                customer_phone=phone,
                chat_history=None,
            )
            
            print(f"Intent: {result['intent']}")
            print(f"\nBot response:")
            print("-" * 100)
            print(result["answer"])
            print("-" * 100)
            
            entities = result.get('extracted_entities', {})
            # Show only non-None entities
            display_entities = {k: v for k, v in entities.items() if v is not None}
            if display_entities:
                print(f"\nExtracted entities: {json.dumps(display_entities, indent=2, default=str, ensure_ascii=False)}")
            
            # Verification
            print(f"\n✅ Test {i} completed")
            
        except Exception as e:
            print(f"\n❌ Test {i} FAILED with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*100)
    print("✓ ALL TESTS COMPLETED")
    print("="*100)


async def main():
    try:
        await test_informal_inputs()
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
