"""Real I/O backends for the Lumon CLI, sandboxed to a root directory."""

from __future__ import annotations

import fnmatch
import os
import subprocess


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

    def delete(self, path: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "file not found"}
        try:
            os.remove(resolved)
            return {"tag": "ok"}
        except OSError:
            return {"tag": "error", "value": "file not found"}

    def find(self, path: str, pattern: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "directory not found"}
        try:
            matches: list[str] = []
            for dirpath, _dirnames, filenames in os.walk(resolved):
                for name in filenames:
                    if fnmatch.fnmatch(name, pattern):
                        full = os.path.join(dirpath, name)
                        matches.append(os.path.relpath(full, resolved))
            return {"tag": "ok", "value": sorted(matches)}
        except OSError:
            return {"tag": "error", "value": "directory not found"}

    def grep(self, path: str, pattern: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "directory not found"}
        try:
            matches: list[str] = []
            for dirpath, _dirnames, filenames in os.walk(resolved):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, resolved)
                    try:
                        with open(full, encoding="utf-8") as f:
                            for lineno, line in enumerate(f, 1):
                                if pattern in line:
                                    matches.append(f"{rel}:{lineno}:{line.rstrip()}")
                    except (OSError, UnicodeDecodeError):
                        continue
            return {"tag": "ok", "value": matches}
        except OSError:
            return {"tag": "error", "value": "directory not found"}

    def head(self, path: str, n: float) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "file not found"}
        try:
            with open(resolved, encoding="utf-8") as f:
                lines = f.read().splitlines()
            return {"tag": "ok", "value": "\n".join(lines[: int(n)])}
        except (OSError, UnicodeDecodeError):
            return {"tag": "error", "value": "file not found"}

    def tail(self, path: str, n: float) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "file not found"}
        try:
            with open(resolved, encoding="utf-8") as f:
                lines = f.read().splitlines()
            count = int(n)
            selected = lines[-count:] if count < len(lines) else lines
            return {"tag": "ok", "value": "\n".join(selected)}
        except (OSError, UnicodeDecodeError):
            return {"tag": "error", "value": "file not found"}

    def replace(self, path: str, old: str, new: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "file not found"}
        try:
            with open(resolved, encoding="utf-8") as f:
                content = f.read()
            content = content.replace(old, new)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return {"tag": "ok"}
        except (OSError, UnicodeDecodeError):
            return {"tag": "error", "value": "file not found"}


class RealGit:
    """Git backend that runs git commands in a root directory."""

    def __init__(self, root: str = ".") -> None:
        self.root = os.path.realpath(root)

    def status(self) -> dict:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok", "value": result.stdout}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def log(self, n: float) -> dict:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{int(n)}"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            entries = [line for line in result.stdout.splitlines() if line]
            return {"tag": "ok", "value": entries}
        except OSError as e:
            return {"tag": "error", "value": str(e)}
