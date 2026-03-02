"""Lumon interpreter error types and envelope builders."""

from __future__ import annotations


class LumonError(Exception):
    """Interpreter error — halts execution and produces structured JSON."""

    def __init__(
        self,
        message: str,
        *,
        function: str | None = None,
        trace: list[str] | None = None,
        inputs: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.function = function
        self.trace = trace or []
        self.inputs = inputs or {}

    def to_envelope(self) -> dict:
        envelope: dict = {"type": "error", "message": self.message}
        if self.function:
            envelope["function"] = self.function
        if self.trace:
            envelope["trace"] = self.trace
        if self.inputs:
            envelope["inputs"] = self.inputs
        return envelope


class ReturnSignal(Exception):
    """Control flow signal for explicit `return` in implement blocks."""

    def __init__(self, value: object):
        self.value = value


class AskSignal(Exception):
    """Control flow signal when `ask` is encountered."""

    def __init__(self, envelope: dict):
        self.envelope = envelope


class SpawnSignal(Exception):
    """Control flow signal when `spawn` is encountered."""

    def __init__(self, envelope: dict):
        self.envelope = envelope
