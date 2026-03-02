"""Real I/O backends for the Lumon CLI, sandboxed to a root directory."""

from __future__ import annotations

import os


class RealFS:
    """Filesystem backend that constrains all operations to a root directory."""

    def __init__(self, root: str = ".") -> None:
        self.root = os.path.realpath(root)

    def _resolve(self, path: str) -> str | None:
        """Resolve path relative to root. Returns None if outside root."""
        if os.path.isabs(path):
            real = os.path.realpath(path)
        else:
            real = os.path.realpath(os.path.join(self.root, path))
        if real != self.root and not real.startswith(self.root + os.sep):
            return None
        return real

    def read(self, path: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "file not found"}
        try:
            with open(resolved, encoding="utf-8") as f:
                return {"tag": "ok", "value": f.read()}
        except (OSError, UnicodeDecodeError):
            return {"tag": "error", "value": "file not found"}

    def write(self, path: str, content: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "permission denied"}
        try:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return {"tag": "ok"}
        except OSError:
            return {"tag": "error", "value": "permission denied"}

    def list_dir(self, path: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "directory not found"}
        try:
            entries = sorted(os.listdir(resolved))
            return {"tag": "ok", "value": entries}
        except OSError:
            return {"tag": "error", "value": "directory not found"}
