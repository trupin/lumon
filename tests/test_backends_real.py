"""Tests for lumon.backends — RealFS and RealGit with real filesystem."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from lumon.backends import RealFS, RealGit


class TestRealFSRead:
    def test_read_existing_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        f = os.path.join(root, "test.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("hello")
        fs = RealFS(root)
        result = fs.read("test.txt")
        assert result == {"tag": "ok", "value": "hello"}

    def test_read_missing_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.read("nope.txt")
        assert result["tag"] == "error"

    def test_read_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.read("../../../etc/passwd")
        assert result["tag"] == "error"

    def test_read_absolute_path_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.read("/etc/passwd")
        assert result["tag"] == "error"


class TestRealFSWrite:
    def test_write_new_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        fs = RealFS(root)
        result = fs.write("output.txt", "content")
        assert result == {"tag": "ok"}
        assert Path(os.path.join(root, "output.txt")).read_text(encoding="utf-8") == "content"

    def test_write_creates_subdirs(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.write("sub/dir/file.txt", "data")
        assert result == {"tag": "ok"}
        assert os.path.isfile(os.path.join(str(tmp_path), "sub", "dir", "file.txt"))

    def test_write_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.write("../../evil.txt", "bad")
        assert result["tag"] == "error"


class TestRealFSListDir:
    def test_list_dir(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        Path(os.path.join(root, "a.txt")).touch()
        Path(os.path.join(root, "b.txt")).touch()
        fs = RealFS(root)
        result = fs.list_dir(".")
        assert result["tag"] == "ok"
        assert "a.txt" in result["value"]
        assert "b.txt" in result["value"]

    def test_list_dir_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.list_dir("nonexistent")
        assert result["tag"] == "error"

    def test_list_dir_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.list_dir("../../..")
        assert result["tag"] == "error"


class TestRealFSDelete:
    def test_delete_existing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        f = os.path.join(root, "del.txt")
        Path(f).touch()
        fs = RealFS(root)
        result = fs.delete("del.txt")
        assert result == {"tag": "ok"}
        assert not os.path.exists(f)

    def test_delete_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.delete("nope.txt")
        assert result["tag"] == "error"

    def test_delete_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.delete("../../evil.txt")
        assert result["tag"] == "error"


class TestRealFSFind:
    def test_find_matching(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        os.makedirs(os.path.join(root, "sub"))
        Path(os.path.join(root, "a.txt")).touch()
        Path(os.path.join(root, "sub", "b.txt")).touch()
        Path(os.path.join(root, "c.py")).touch()
        fs = RealFS(root)
        result = fs.find(".", "*.txt")
        assert result["tag"] == "ok"
        assert "a.txt" in result["value"]
        assert os.path.join("sub", "b.txt") in result["value"]
        assert "c.py" not in result["value"]

    def test_find_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.find("../../..", "*.txt")
        assert result["tag"] == "error"


class TestRealFSGrep:
    def test_grep_matching(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        with open(os.path.join(root, "a.txt"), "w", encoding="utf-8") as f:
            f.write("hello world\ngoodbye\nhello again\n")
        fs = RealFS(root)
        result = fs.grep(".", "hello")
        assert result["tag"] == "ok"
        assert len(result["value"]) == 2

    def test_grep_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.grep("../../..", "pattern")
        assert result["tag"] == "error"


class TestRealFSHeadTail:
    def test_head(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3\nline4\n")
        fs = RealFS(root)
        result = fs.head("f.txt", 2)
        assert result["tag"] == "ok"
        assert result["value"] == "line1\nline2"

    def test_head_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.head("nope.txt", 2)
        assert result["tag"] == "error"

    def test_head_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.head("../../etc/passwd", 1)
        assert result["tag"] == "error"

    def test_tail(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3\nline4")
        fs = RealFS(root)
        result = fs.tail("f.txt", 2)
        assert result["tag"] == "ok"
        assert result["value"] == "line3\nline4"

    def test_tail_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.tail("nope.txt", 2)
        assert result["tag"] == "error"

    def test_tail_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.tail("../../etc/passwd", 1)
        assert result["tag"] == "error"


class TestRealFSReplace:
    def test_replace_content(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as f:
            f.write("hello world")
        fs = RealFS(root)
        result = fs.replace("f.txt", "hello", "goodbye")
        assert result == {"tag": "ok"}
        assert Path(os.path.join(root, "f.txt")).read_text(encoding="utf-8") == "goodbye world"

    def test_replace_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.replace("nope.txt", "a", "b")
        assert result["tag"] == "error"

    def test_replace_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.replace("../../evil.txt", "a", "b")
        assert result["tag"] == "error"


class TestRealGit:
    def test_status_in_git_repo(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
        git = RealGit(root)
        result = git.status()
        assert result["tag"] == "ok"

    def test_status_not_git_repo(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        git = RealGit(str(tmp_path))
        result = git.status()
        assert result["tag"] == "error"

    def test_log_in_git_repo(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
        Path(os.path.join(root, "f.txt")).touch()
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, capture_output=True, check=True)
        git = RealGit(root)
        result = git.log(5)
        assert result["tag"] == "ok"
        assert len(result["value"]) == 1

    def test_log_not_git_repo(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        git = RealGit(str(tmp_path))
        result = git.log(5)
        assert result["tag"] == "error"
