from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@dataclass(frozen=True)
class MockPaymentIntent:
    payment_intent_id: str
    payment_link: str
    expires_at: datetime


class MockPaymentService:
    """Generates mock payment intents for local and integration testing."""

    def create_payment_intent(self, *, amount: float, currency: str) -> MockPaymentIntent:
        intent_id = f"pi_mock_{uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        payment_link = f"https://mock-payments.local/pay/{intent_id}?amount={amount}&currency={currency}"
        return MockPaymentIntent(
            payment_intent_id=intent_id,
            payment_link=payment_link,
            expires_at=expires_at,
        )
