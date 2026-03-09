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


class TestRealFSMkdir:
    def test_creates_directory(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        fs = RealFS(root)
        result = fs.mkdir("newdir")
        assert result["tag"] == "ok"
        assert os.path.isdir(os.path.join(root, "newdir"))

    def test_creates_intermediate_parents(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        fs = RealFS(root)
        result = fs.mkdir("a/b/c")
        assert result["tag"] == "ok"
        assert os.path.isdir(os.path.join(root, "a", "b", "c"))

    def test_existing_dir_succeeds(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        os.makedirs(os.path.join(root, "existing"))
        fs = RealFS(root)
        result = fs.mkdir("existing")
        assert result["tag"] == "ok"

    def test_outside_root_blocked(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.mkdir("../../evil")
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

    def test_list_dir_recursive(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        os.makedirs(os.path.join(root, "sub"))
        Path(os.path.join(root, "a.txt")).touch()
        Path(os.path.join(root, "sub", "b.txt")).touch()
        fs = RealFS(root)
        result = fs.list_dir(".", recursive=True)
        assert result["tag"] == "ok"
        assert sorted(result["value"]) == ["a.txt", "sub/b.txt"]


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


class TestRealFSDeleteDir:
    def test_delete_dir_existing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        sub = os.path.join(root, "mydir")
        os.makedirs(sub)
        Path(os.path.join(sub, "file.txt")).touch()
        fs = RealFS(root)
        result = fs.delete_dir("mydir")
        assert result == {"tag": "ok"}
        assert not os.path.exists(sub)

    def test_delete_dir_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.delete_dir("nope")
        assert result["tag"] == "error"

    def test_delete_dir_outside_root(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.delete_dir("../../evil")
        assert result["tag"] == "error"

    def test_delete_dir_root_blocked(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        fs = RealFS(str(tmp_path))
        result = fs.delete_dir(".")
        assert result["tag"] == "error"
        assert "root" in result["value"]


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

    @staticmethod
    def _init_repo(tmp_path: object) -> tuple[str, RealGit]:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
        return root, RealGit(root)

    def test_init_creates_repo(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        git = RealGit(root)
        result = git.init()
        assert result["tag"] == "ok"
        assert os.path.isdir(os.path.join(root, ".git"))

    def test_add_stages_file(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "file.txt")).write_text("hello")
        result = git.add("file.txt")
        assert result["tag"] == "ok"

    def test_add_nonexistent_errors(self, tmp_path: object) -> None:
        _root, git = self._init_repo(tmp_path)
        result = git.add("nonexistent.txt")
        assert result["tag"] == "error"

    def test_commit_creates_commit(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "file.txt")).write_text("hello")
        git.add("file.txt")
        result = git.commit("initial commit")
        assert result["tag"] == "ok"
        assert isinstance(result["value"], str)
        assert len(result["value"]) > 0

    def test_commit_nothing_staged_errors(self, tmp_path: object) -> None:
        _root, git = self._init_repo(tmp_path)
        # Need at least one commit for git to exist properly
        result = git.commit("empty")
        assert result["tag"] == "error"

    def test_diff_shows_changes(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        fpath = os.path.join(root, "file.txt")
        Path(fpath).write_text("hello")
        git.add("file.txt")
        git.commit("init")
        Path(fpath).write_text("hello world")
        result = git.diff()
        assert result["tag"] == "ok"
        assert "hello world" in result["value"]

    def test_diff_staged_shows_staged(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        fpath = os.path.join(root, "file.txt")
        Path(fpath).write_text("hello")
        git.add("file.txt")
        git.commit("init")
        Path(fpath).write_text("updated")
        git.add("file.txt")
        result = git.diff_staged()
        assert result["tag"] == "ok"
        assert "updated" in result["value"]

    def test_branch_and_list(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        result = git.branch("feature")
        assert result["tag"] == "ok"
        branches = git.branch_list()
        assert branches["tag"] == "ok"
        assert "feature" in branches["value"]

    def test_branch_duplicate_errors(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        git.branch("feature")
        result = git.branch("feature")
        assert result["tag"] == "error"

    def test_checkout_switches_branch(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        git.branch("feature")
        result = git.checkout("feature")
        assert result["tag"] == "ok"

    def test_checkout_bad_ref_errors(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        result = git.checkout("nonexistent")
        assert result["tag"] == "error"

    def test_reset_unstages_file(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        Path(os.path.join(root, "f.txt")).write_text("changed")
        git.add("f.txt")
        result = git.reset("f.txt")
        assert result["tag"] == "ok"
        # After reset, diff_staged should be empty for that file
        staged = git.diff_staged()
        assert "changed" not in staged["value"]

    def test_show_commit(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        result = git.show("HEAD")
        assert result["tag"] == "ok"
        assert "init" in result["value"]

    def test_show_bad_ref_errors(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        result = git.show("nonexistent_ref_abc")
        assert result["tag"] == "error"

    def test_tag_and_list(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        result = git.tag("v1.0")
        assert result["tag"] == "ok"
        tags = git.tag_list()
        assert tags["tag"] == "ok"
        assert "v1.0" in tags["value"]

    def test_tag_duplicate_errors(self, tmp_path: object) -> None:
        root, git = self._init_repo(tmp_path)
        Path(os.path.join(root, "f.txt")).write_text("x")
        git.add("f.txt")
        git.commit("init")
        git.tag("v1.0")
        result = git.tag("v1.0")
        assert result["tag"] == "error"

    def test_not_git_repo_errors(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        # Test each function individually with a fresh non-repo directory
        for name, fn_factory in [
            ("add", lambda g: (g.add, ["f.txt"])),
            ("commit", lambda g: (g.commit, ["msg"])),
            ("diff", lambda g: (g.diff, [])),
            ("diff_staged", lambda g: (g.diff_staged, [])),
            ("branch", lambda g: (g.branch, ["x"])),
            ("branch_list", lambda g: (g.branch_list, [])),
            ("checkout", lambda g: (g.checkout, ["x"])),
            ("reset", lambda g: (g.reset, ["x"])),
            ("show", lambda g: (g.show, ["HEAD"])),
            ("tag", lambda g: (g.tag, ["v1"])),
            ("tag_list", lambda g: (g.tag_list, [])),
        ]:
            subdir = os.path.join(str(tmp_path), name)
            os.makedirs(subdir)
            git = RealGit(subdir)
            fn, args = fn_factory(git)
            result = fn(*args)
            assert result["tag"] == "error", f"{name} should error outside git repo"
