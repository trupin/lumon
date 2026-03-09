"""I/O backends for the Lumon CLI — real (filesystem) and in-memory."""

from __future__ import annotations

import fnmatch
import os
import shutil
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

    def mkdir(self, path: str) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "permission denied"}
        try:
            os.makedirs(resolved, exist_ok=True)
            return {"tag": "ok"}
        except OSError:
            return {"tag": "error", "value": "permission denied"}

    def list_dir(self, path: str, recursive: bool = False) -> dict:
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "directory not found"}
        try:
            if recursive:
                entries: list[str] = []
                for dirpath, _dirnames, filenames in os.walk(resolved):
                    for name in filenames:
                        full = os.path.join(dirpath, name)
                        entries.append(os.path.relpath(full, resolved))
                return {"tag": "ok", "value": sorted(entries)}
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

    def delete_dir(self, path: str) -> dict:
        """Delete a directory and all its contents."""
        resolved = self._resolve(path)
        if resolved is None:
            return {"tag": "error", "value": "directory not found"}
        if resolved == self.root:
            return {"tag": "error", "value": "cannot delete root directory"}
        try:
            shutil.rmtree(resolved)
            return {"tag": "ok"}
        except OSError:
            return {"tag": "error", "value": "directory not found"}

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
    """Git backend that runs git commands from the repository root.

    Automatically discovers the git repo root via ``git rev-parse
    --show-toplevel``.  Falls back to the given *root* directory when
    the discovery fails (e.g. not inside a git repo yet — ``git.init``
    will still work).
    """

    def __init__(self, root: str = ".") -> None:
        real = os.path.realpath(root)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=real,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                real = result.stdout.strip()
        except OSError:
            pass
        self.root = real

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def status(self) -> dict:
        try:
            result = self._run(["status", "--porcelain"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok", "value": result.stdout}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def log(self, n: float) -> dict:
        try:
            result = self._run(["log", "--oneline", f"-{int(n)}"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            entries = [line for line in result.stdout.splitlines() if line]
            return {"tag": "ok", "value": entries}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def init(self) -> dict:
        try:
            result = self._run(["init"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def add(self, path: str) -> dict:
        try:
            result = self._run(["add", path])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def commit(self, message: str) -> dict:
        try:
            result = self._run(["commit", "-m", message])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            # Reliably get the short hash of the commit we just created
            rev = self._run(["rev-parse", "--short", "HEAD"])
            commit_hash = rev.stdout.strip() if rev.returncode == 0 else ""
            return {"tag": "ok", "value": commit_hash}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def diff(self) -> dict:
        try:
            result = self._run(["diff"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok", "value": result.stdout}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def diff_staged(self) -> dict:
        try:
            result = self._run(["diff", "--staged"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok", "value": result.stdout}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def branch(self, name: str) -> dict:
        try:
            result = self._run(["branch", name])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def branch_list(self) -> dict:
        try:
            result = self._run(["branch", "--format=%(refname:short)"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            branches = [line for line in result.stdout.splitlines() if line]
            return {"tag": "ok", "value": branches}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def checkout(self, ref: str) -> dict:
        try:
            result = self._run(["checkout", ref])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def reset(self, path: str) -> dict:
        try:
            result = self._run(["reset", "--", path])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def show(self, ref: str) -> dict:
        try:
            result = self._run(["show", "--stat", ref])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok", "value": result.stdout}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def tag(self, name: str) -> dict:
        try:
            result = self._run(["tag", name])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            return {"tag": "ok"}
        except OSError as e:
            return {"tag": "error", "value": str(e)}

    def tag_list(self) -> dict:
        try:
            result = self._run(["tag", "--list"])
            if result.returncode != 0:
                return {"tag": "error", "value": result.stderr.strip()}
            tags = [line for line in result.stdout.splitlines() if line]
            return {"tag": "ok", "value": tags}
        except OSError as e:
            return {"tag": "error", "value": str(e)}


# ---------------------------------------------------------------------------
# In-memory backends for test isolation
# ---------------------------------------------------------------------------


class MemoryFS:
    """In-memory filesystem for test isolation.

    Same interface as RealFS but backed by a dict.
    Seeded via mock_io() in Lumon test blocks or directly via seed().
    """

    def __init__(self, files: dict[str, str] | None = None, *, root: str = "/sandbox") -> None:
        self.root = os.path.normpath(root)
        self._files: dict[str, str] = {}
        self._dirs: set[str] = set()
        for path, content in (files or {}).items():
            self._files[self._normalise(path)] = content

    def _normalise(self, path: str) -> str:
        if not os.path.isabs(path):
            path = os.path.join(self.root, path)
        return os.path.normpath(path)

    def _is_within_root(self, normalised: str) -> bool:
        if self.root == os.sep:
            return True
        return normalised == self.root or normalised.startswith(self.root + os.sep)

    def seed(self, files: dict[str, str]) -> None:
        """Add files to the in-memory filesystem."""
        for path, content in files.items():
            self._files[self._normalise(path)] = content

    def clear(self) -> None:
        """Remove all files."""
        self._files.clear()
        self._dirs.clear()

    def read(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm) or norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        return {"tag": "ok", "value": self._files[norm]}

    def write(self, path: str, content: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "permission denied"}
        self._files[norm] = content
        return {"tag": "ok"}

    def mkdir(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "permission denied"}
        # Register this directory and all intermediate parents
        parts = os.path.relpath(norm, self.root).split(os.sep)
        current = self.root
        for part in parts:
            current = os.path.join(current, part)
            self._dirs.add(os.path.normpath(current))
        return {"tag": "ok"}

    def _is_known_dir(self, norm: str) -> bool:
        """Check if a normalised path is a known directory (has files or was mkdir'd)."""
        prefix = norm + os.sep if norm != os.sep else os.sep
        if norm in self._dirs:
            return True
        return any(fp.startswith(prefix) for fp in self._files)

    def list_dir(self, path: str, recursive: bool = False) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "directory not found"}
        prefix = norm + os.sep if norm != os.sep else os.sep
        if recursive:
            entries: list[str] = []
            for fpath in self._files:
                if fpath.startswith(prefix):
                    entries.append(fpath[len(prefix):])
            for dpath in self._dirs:
                if dpath.startswith(prefix):
                    entries.append(dpath[len(prefix):])
            if not entries and not self._is_known_dir(norm):
                return {"tag": "error", "value": "directory not found"}
            return {"tag": "ok", "value": sorted(set(entries))}
        top_entries: set[str] = set()
        for fpath in self._files:
            if fpath.startswith(prefix):
                rest = fpath[len(prefix):]
                top_entries.add(rest.split(os.sep)[0])
        for dpath in self._dirs:
            if dpath.startswith(prefix):
                rest = dpath[len(prefix):]
                top_entries.add(rest.split(os.sep)[0])
        if not top_entries and norm not in self._files and not self._is_known_dir(norm):
            return {"tag": "error", "value": "directory not found"}
        return {"tag": "ok", "value": sorted(top_entries)}

    def delete(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm) or norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        del self._files[norm]
        return {"tag": "ok"}

    def delete_dir(self, path: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm):
            return {"tag": "error", "value": "directory not found"}
        if norm == self.root:
            return {"tag": "error", "value": "cannot delete root directory"}
        prefix = norm + os.sep
        to_delete = [fp for fp in self._files if fp.startswith(prefix) or fp == norm]
        if not to_delete:
            return {"tag": "error", "value": "directory not found"}
        for fp in to_delete:
            del self._files[fp]
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
                for lineno, line in enumerate(self._files[fpath].splitlines(), 1):
                    if pattern in line:
                        matches.append(f"{rel}:{lineno}:{line}")
        return {"tag": "ok", "value": matches}

    def head(self, path: str, n: float) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm) or norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        lines = self._files[norm].splitlines()
        return {"tag": "ok", "value": "\n".join(lines[: int(n)])}

    def tail(self, path: str, n: float) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm) or norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        lines = self._files[norm].splitlines()
        count = int(n)
        selected = lines[-count:] if count < len(lines) else lines
        return {"tag": "ok", "value": "\n".join(selected)}

    def replace(self, path: str, old: str, new: str) -> dict:
        norm = self._normalise(path)
        if not self._is_within_root(norm) or norm not in self._files:
            return {"tag": "error", "value": "file not found"}
        self._files[norm] = self._files[norm].replace(old, new)
        return {"tag": "ok"}


class MemoryGit:
    """In-memory git backend for test isolation."""

    def __init__(
        self,
        *,
        status_output: str = "",
        log_entries: list[str] | None = None,
        branches: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._status = status_output
        self._log = log_entries or []
        self._branches = branches or []
        self._tags = tags or []
        self._staged: list[str] = []
        self._commits: list[str] = []
        self._current_branch = self._branches[0] if self._branches else "main"
        self._diff = ""
        self._diff_staged = ""
        self._show: dict[str, str] = {}

    def status(self) -> dict:
        return {"tag": "ok", "value": self._status}

    def log(self, n: float) -> dict:
        return {"tag": "ok", "value": self._log[: int(n)]}

    def init(self) -> dict:
        return {"tag": "ok"}

    def add(self, path: str) -> dict:
        self._staged.append(path)
        return {"tag": "ok"}

    def commit(self, message: str) -> dict:
        if not self._staged:
            return {"tag": "error", "value": "nothing to commit"}
        commit_hash = f"{len(self._commits):07x}"
        self._commits.append(f"{commit_hash} {message}")
        self._log.insert(0, f"{commit_hash} {message}")
        self._staged.clear()
        return {"tag": "ok", "value": commit_hash}

    def diff(self) -> dict:
        return {"tag": "ok", "value": self._diff}

    def diff_staged(self) -> dict:
        return {"tag": "ok", "value": self._diff_staged}

    def branch(self, name: str) -> dict:
        if name in self._branches:
            return {"tag": "error", "value": f"branch '{name}' already exists"}
        self._branches.append(name)
        return {"tag": "ok"}

    def branch_list(self) -> dict:
        return {"tag": "ok", "value": list(self._branches)}

    def checkout(self, ref: str) -> dict:
        if ref in self._branches:
            self._current_branch = ref
            return {"tag": "ok"}
        return {"tag": "error", "value": f"pathspec '{ref}' did not match"}

    def reset(self, path: str) -> dict:
        if path in self._staged:
            self._staged.remove(path)
        return {"tag": "ok"}

    def show(self, ref: str) -> dict:
        if ref in self._show:
            return {"tag": "ok", "value": self._show[ref]}
        # Default: return first log entry if available
        if self._log:
            return {"tag": "ok", "value": self._log[0]}
        return {"tag": "error", "value": f"bad revision '{ref}'"}

    def tag(self, name: str) -> dict:
        if name in self._tags:
            return {"tag": "error", "value": f"tag '{name}' already exists"}
        self._tags.append(name)
        return {"tag": "ok"}

    def tag_list(self) -> dict:
        return {"tag": "ok", "value": list(self._tags)}
