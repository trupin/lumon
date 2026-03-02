"""Convert Lumon runtime values to JSON-serializable Python objects."""

from __future__ import annotations

from lumon.values import LumonTag


def serialize(value: object) -> object:
    """Convert a Lumon runtime value to a JSON-serializable Python value."""
    if isinstance(value, LumonTag):
        if value.payload is None:
            return {"tag": value.name}
        return {"tag": value.name, "value": serialize(value.payload)}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    # str, int, float, bool, None pass through directly
    return value
