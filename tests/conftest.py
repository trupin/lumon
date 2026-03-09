from dataclasses import dataclass, field

import pytest

from lumon import interpret
from lumon.backends import MemoryFS as MockFS
from lumon.backends import MemoryGit as MockGit


# ---------------------------------------------------------------------------
# RunResult — structured wrapper around interpreter output
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Wraps the interpreter's JSON output for convenient test assertions."""

    output: dict = field(default_factory=dict)

    # -- convenience properties ---------------------------------------------

    @property
    def raw(self) -> dict:
        """The full output dict."""
        return self.output

    @property
    def type(self) -> str:
        return self.output.get("type", "")

    @property
    def value(self):
        """The 'value' field from a result envelope."""
        return self.output.get("value")

    @property
    def error(self) -> dict | None:
        if self.type == "error":
            return self.output
        return None

    @property
    def asks(self) -> list[dict]:
        """List of ask requests (for coroutine tests)."""
        if self.type == "ask":
            return [self.output]
        return []

    @property
    def spawns(self) -> list[dict]:
        """List of spawn requests."""
        if self.type == "spawn_batch":
            return [self.output]
        return []

    # -- tag helpers --------------------------------------------------------

    @property
    def tag_name(self) -> str | None:
        v = self.value
        if isinstance(v, dict) and "tag" in v:
            return v["tag"]
        return None

    @property
    def tag_value(self):
        v = self.value
        if isinstance(v, dict) and "tag" in v:
            return v.get("value")
        return None

    def is_ok(self) -> bool:
        return self.tag_name == "ok"

    def is_error(self) -> bool:
        return self.type == "error" or self.tag_name == "error"


# ---------------------------------------------------------------------------
# LumonRunner — test-friendly wrapper around interpret()
# ---------------------------------------------------------------------------

class LumonRunner:
    """Wraps the interpret() function for convenient test usage."""

    def run(
        self,
        code: str,
        *,
        io: MockFS | None = None,
        git: MockGit | None = None,
    ) -> RunResult:
        raw = interpret(code, io_backend=io, git_backend=git)
        return RunResult(output=raw)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> LumonRunner:
    return LumonRunner()


@pytest.fixture
def mock_fs() -> MockFS:
    return MockFS()
