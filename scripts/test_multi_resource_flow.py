"""
Test script to verify the multi-resource booking flow.
Simulates the API request to test the new agent behavior.
"""

import asyncio
import json
import sys
from uuid import UUID

sys.path.insert(0, "d:\\Projects\\automation-backend\\ai-sales-booking-fastapi")

from app.services.ai_engine import AIOrchestrator


async def test_multi_resource_flow():
    """Test the booking flow when user doesn't specify a doctor."""
    
    orchestrator = AIOrchestrator()
    
    tenant_id = UUID("f0a6ad3c-b2c1-499e-8082-c6371940845e")
    customer_phone = "59178945612"
    
    print("="*80)
    print("TEST 1: User asks for availability WITHOUT specifying a doctor")
    print("="*80)
    print('\nUser message: "Quisiera saber si tiene horarios disponibles"')
    print()
    
    result = await orchestrator.answer_customer(
        tenant_id=tenant_id,
        user_message="Quisiera saber si tiene horarios disponibles",
        customer_phone=customer_phone,
        chat_history=None,
    )
    
    print(f"Intent: {result['intent']}")
    print(f"\nBot response:")
    print("-" * 80)
    print(result["answer"])
    print("-" * 80)
    print(f"\nExtracted entities: {json.dumps(result.get('extracted_entities', {}), indent=2, default=str)}")
    
    print("\n" + "="*80)
    print("TEST 2: User asks for availability WITH specific doctor")
    print("="*80)
    print('\nUser message: "Quisiera saber si tiene horarios disponibles con Dr. Penafiel"')
    print()
    
    result2 = await orchestrator.answer_customer(
        tenant_id=tenant_id,
        user_message="Quisiera saber si tiene horarios disponibles con Dr. Penafiel",
        customer_phone=customer_phone,
        chat_history=None,
    )
    
    print(f"Intent: {result2['intent']}")
    print(f"\nBot response:")
    print("-" * 80)
    print(result2["answer"])
    print("-" * 80)
    print(f"\nExtracted entities: {json.dumps(result2.get('extracted_entities', {}), indent=2, default=str)}")
    
    print("\n" + "="*80)
    print("TEST 3: User asks with different doctor name")
    print("="*80)
    print('\nUser message: "Tiene turnos con Dra. Yrene?"')
    print()
    
    result3 = await orchestrator.answer_customer(
        tenant_id=tenant_id,
        user_message="Tiene turnos con Dra. Yrene?",
        customer_phone=customer_phone,
        chat_history=None,
    )
    
    print(f"Intent: {result3['intent']}")
    print(f"\nBot response:")
    print("-" * 80)
    print(result3["answer"])
    print("-" * 80)
    print(f"\nExtracted entities: {json.dumps(result3.get('extracted_entities', {}), indent=2, default=str)}")
    
    print("\n" + "="*80)
    print("✓ ALL TESTS COMPLETED")
    print("="*80)


async def main():
    try:
        await test_multi_resource_flow()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
