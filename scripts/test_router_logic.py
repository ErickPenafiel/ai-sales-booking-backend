from __future__ import annotations

from app.services.ai_engine import AIOrchestrator


def test_extract_json_from_llm() -> None:
    text = """Claro, aqui va:\n```json\n{\"intent\":\"BOOKING\"}\n```\nGracias"""
    payload = AIOrchestrator.extract_json_from_llm(text)
    assert payload is not None
    assert payload.get("intent") == "BOOKING"


def test_extract_json_from_llm_invalid() -> None:
    text = "respuesta sin json"
    payload = AIOrchestrator.extract_json_from_llm(text)
    assert payload is None


def test_fallback_intent_priority_info() -> None:
    msg = "Cuanto tiempo antes tengo avisar para cancelar una cita"
    intent = AIOrchestrator.fallback_intent_classifier(msg)
    assert intent == "INFO"


def test_fallback_intent_booking() -> None:
    msg = "Quiero ver horarios disponibles para mañana"
    intent = AIOrchestrator.fallback_intent_classifier(msg)
    assert intent == "BOOKING"


def test_fallback_intent_default_info() -> None:
    msg = "Hola, buen dia"
    intent = AIOrchestrator.fallback_intent_classifier(msg)
    assert intent == "INFO"


if __name__ == "__main__":
    tests = [
        test_extract_json_from_llm,
        test_extract_json_from_llm_invalid,
        test_fallback_intent_priority_info,
        test_fallback_intent_booking,
        test_fallback_intent_default_info,
    ]
    ok = 0
    for test_fn in tests:
        test_fn()
        ok += 1
    print(f"Router logic tests passed: {ok}/{len(tests)}")
