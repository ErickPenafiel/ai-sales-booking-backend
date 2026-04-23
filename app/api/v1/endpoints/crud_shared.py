"""
Shared helpers for CRUD endpoint modules.
"""

from uuid import UUID


def model_to_dict(obj) -> dict:
    """Convert SQLAlchemy model to dict."""
    result = {}
    for key in obj.__dict__:
        if key.startswith("_"):
            continue
        value = getattr(obj, key)
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif hasattr(value, "value"):
            result[key] = value.value
        else:
            result[key] = value
    return result
