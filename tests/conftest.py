import fnmatch
import os
from dataclasses import dataclass, field

import pytest

from lumon import interpret


# ---------------------------------------------------------------------------
# MockFS — in-memory filesystem for io.* built-ins
# ---------------------------------------------------------------------------

class MockFS:
    """In-memory filesystem seeded with {path: content} pairs.

    Enforces root-directory boundary: paths resolving outside the root
    are treated as non-existent.
    """

    def __init__(self, files: dict[str, str] | None = None, *, root: str = "/sandbox"):
        self.root = os.path.normpath(root)
        # Normalise keys so lookups are consistent
        self._files: dict[str, str] = {}
        for path, content in (files or {}).items():
            self._files[self._normalise(path)] = content

    # -- internal helpers ---------------------------------------------------

    def _normalise(self, path: str) -> str:
        """Resolve path relative to root; return normalised absolute path."""
        if not os.path.isabs(path):
            path = os.path.join(self.root, path)
        return os.path.normpath(path)

    def _is_within_root(self, normalised: str) -> bool:
        if self.root == os.sep:
            return True
        return normalised == self.root or normalised.startswith(self.root + os.sep)

    # -- public API (mirrors io.* semantics) --------------------------------

    def read(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "file not found"}
        if norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        return {"tag": "ok", "value": self._files[norm]}

    def write(self, path: str, content: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "permission denied"}
        self._files[norm] = content
        return {"tag": "ok"}

    def list_dir(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "directory not found"}
        prefix = norm + os.sep if norm != os.sep else os.sep
        entries: set[str] = set()
        for fpath in self._files:
            if fpath.startswith(prefix):
                # First component after the prefix
                rest = fpath[len(prefix):]
                entry = rest.split(os.sep)[0]
                entries.add(entry)
        if not entries and norm not in self._files:
            # Check if path itself is a known directory
            # (has any files under it)
            has_children = any(fp.startswith(prefix) for fp in self._files)
            if not has_children:
                return {"tag": "error", "value": "directory not found"}
        return {"tag": "ok", "value": sorted(entries)}

    def delete(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "file not found"}
        if norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        del self._files[norm]
        return {"tag": "ok"}

    def find(self, path: str, pattern: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "directory not found"}
        prefix = norm + os.sep if norm != os.sep else os.sep
        matches: list[str] = []
        for fpath in self._files:
            if fpath.startswith(prefix) or fpath == norm:
                rel = fpath[len(prefix):]
                basename = rel.rsplit(os.sep, 1)[-1] if os.sep in rel else rel
                if fnmatch.fnmatch(basename, pattern):
                    matches.append(rel)
        return {"tag": "ok", "value": sorted(matches)}

    def grep(self, path: str, pattern: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "directory not found"}
        prefix = norm + os.sep if norm != os.sep else os.sep
        matches: list[str] = []
        for fpath in sorted(self._files):
            if fpath.startswith(prefix):
                rel = fpath[len(prefix):]
                content = self._files[fpath]
                for lineno, line in enumerate(content.splitlines(), 1):
                    if pattern in line:
                        matches.append(f"{rel}:{lineno}:{line}")
        return {"tag": "ok", "value": matches}

    def head(self, path: str, n: float) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "file not found"}
        if norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        lines = self._files[norm].splitlines()
        return {"tag": "ok", "value": "\n".join(lines[: int(n)])}

    def tail(self, path: str, n: float) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "file not found"}
        if norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        lines = self._files[norm].splitlines()
        count = int(n)
        selected = lines[-count:] if count < len(lines) else lines
        return {"tag": "ok", "value": "\n".join(selected)}

    def replace(self, path: str, old: str, new: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "file not found"}
        if norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        self._files[norm] = self._files[norm].replace(old, new)
        return {"tag": "ok"}


# ---------------------------------------------------------------------------
# MockGit — canned git responses for git.* built-ins
# ---------------------------------------------------------------------------

class MockGit:
    """Canned git responses for git.* built-ins.

    Seeded with status_output and log_entries.
    """

    def __init__(
        self,
        *,
        status_output: str = "",
        log_entries: list[str] | None = None,
    ):
        self._status = status_output
        self._log = log_entries or []

    def status(self) -> dict:
        return {"tag": "ok", "value": self._status}

    def log(self, n: float) -> dict:
        return {"tag": "ok", "value": self._log[: int(n)]}


# ---------------------------------------------------------------------------
# MockHTTP — canned HTTP responses for http.* built-ins
# ---------------------------------------------------------------------------

class MockHTTP:
    """Canned HTTP responses seeded with {url: body} pairs.

    URLs not in the map return :error("unreachable").
    A blacklist can be provided; blacklisted URLs also return :error.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        blacklist: list[str] | None = None,
    ):
        self._responses = dict(responses or {})
        self._blacklist = set(blacklist or [])

    def get(self, url: str) -> dict:
        if url in self._blacklist:
            return {"tag": "error", "value": "unreachable"}
        if url not in self._responses:
            return {"tag": "error", "value": "unreachable"}
        return {"tag": "ok", "value": self._responses[url]}


# ---------------------------------------------------------------------------
# RunResult — structured wrapper around interpreter output
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Wraps the interpreter's JSON output for convenient test assertions."""

    output: dict = field(default_factory=dict)

    # -- convenience properties ---------------------------------------------

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
        http: MockHTTP | None = None,
        git: MockGit | None = None,
    ) -> RunResult:
        raw = interpret(code, io_backend=io, http_backend=http, git_backend=git)
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


@pytest.fixture
def mock_http() -> MockHTTP:
    return MockHTTP()
