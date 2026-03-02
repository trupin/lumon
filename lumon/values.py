"""Lumon runtime value types that don't map directly to Python primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LumonTag:
    """A named label with optional payload: :ok, :error("msg")."""

    name: str
    payload: object = None


@dataclass(frozen=True)
class LumonFunction:
    """A user-defined function or lambda with captured closure environment."""

    params: tuple[str, ...]
    body: object  # AST node (expression or Block)
    closure_env: object  # Environment snapshot
    is_lambda: bool = True


def is_truthy(value: object) -> bool:
    """Lumon truthy/falsy rules: false, none, 0, "", [], {} are falsy."""
    if value is None:
        return False
    if value is False:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, str) and value == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    if isinstance(value, dict) and len(value) == 0:
        return False
    return True
