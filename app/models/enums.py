from __future__ import annotations

from enum import StrEnum


class AppointmentStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class AssetType(StrEnum):
    TEXT = "TEXT"
    PDF = "PDF"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    LOCATION = "LOCATION"
