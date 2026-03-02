"""Tests for Lumon io.* built-ins with MockFS."""

import pytest

from tests.conftest import MockFS


@pytest.fixture
def run(runner):
    def _run(code, *, io=None):
        return runner.run(code, io=io)
    return _run


# ===================================================================
# io.read
# ===================================================================

class TestIoRead:
    def test_read_existing_file(self, run):
        fs = MockFS({"file.md": "hello world"})
        r = run('return io.read("file.md")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "hello world"

    def test_read_missing_file(self, run):
        fs = MockFS()
        r = run('return io.read("missing.md")', io=fs)
        assert r.tag_name == "error"

    def test_read_nested_path(self, run):
        fs = MockFS({"docs/spec.md": "spec content"})
        r = run('return io.read("docs/spec.md")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "spec content"

    def test_read_empty_file(self, run):
        fs = MockFS({"empty.md": ""})
        r = run('return io.read("empty.md")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == ""


# ===================================================================
# io.write
# ===================================================================

class TestIoWrite:
    def test_write_new_file(self, run):
        fs = MockFS()
        r = run('return io.write("new.md", "content")', io=fs)
        assert r.tag_name == "ok"
        # Verify file was written in mock
        assert fs.read("new.md") == {"tag": "ok", "value": "content"}

    def test_write_overwrite_existing(self, run):
        fs = MockFS({"file.md": "old"})
        r = run('return io.write("file.md", "new")', io=fs)
        assert r.tag_name == "ok"
        assert fs.read("file.md") == {"tag": "ok", "value": "new"}

    def test_write_then_read(self, run):
        fs = MockFS()
        r = run(
            'let w = io.write("test.md", "hello")\n'
            'return io.read("test.md")',
            io=fs,
        )
        assert r.tag_name == "ok"
        assert r.tag_value == "hello"

    def test_write_nested_path(self, run):
        fs = MockFS()
        r = run('return io.write("dir/file.md", "content")', io=fs)
        assert r.tag_name == "ok"


# ===================================================================
# io.list_dir
# ===================================================================

class TestIoListDir:
    def test_list_dir_with_files(self, run):
        fs = MockFS({"a.md": "a", "b.md": "b", "c.md": "c"})
        r = run('return io.list_dir(".")', io=fs)
        assert r.tag_name == "ok"
        assert sorted(r.tag_value) == ["a.md", "b.md", "c.md"]

    def test_list_dir_missing(self, run):
        fs = MockFS()
        r = run('return io.list_dir("nonexistent")', io=fs)
        assert r.tag_name == "error"

    def test_list_dir_nested(self, run):
        fs = MockFS({"dir/a.md": "a", "dir/b.md": "b"})
        r = run('return io.list_dir("dir")', io=fs)
        assert r.tag_name == "ok"
        assert sorted(r.tag_value) == ["a.md", "b.md"]

    def test_list_dir_shows_subdirs(self, run):
        fs = MockFS({"dir/sub/file.md": "x"})
        r = run('return io.list_dir("dir")', io=fs)
        assert r.tag_name == "ok"
        assert "sub" in r.tag_value


# ===================================================================
# Path security
# ===================================================================

class TestIoPathSecurity:
    def test_path_traversal_blocked(self, run):
        """../../etc/passwd should return :error, not read outside root."""
        fs = MockFS()
        r = run('return io.read("../../etc/passwd")', io=fs)
        assert r.tag_name == "error"

    def test_path_normalization(self, run):
        """./dir/../file.md should resolve to file.md."""
        fs = MockFS({"file.md": "content"})
        r = run('return io.read("./dir/../file.md")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "content"

    def test_absolute_path_outside_root(self, run):
        fs = MockFS()
        r = run('return io.read("/etc/passwd")', io=fs)
        assert r.tag_name == "error"

    def test_write_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.write("../../evil.md", "pwned")', io=fs)
        assert r.tag_name == "error"

    def test_error_indistinguishable_from_not_found(self, run):
        """Path restriction errors look the same as file-not-found errors."""
        fs = MockFS()
        r_traversal = run('return io.read("../../etc/passwd")', io=fs)
        r_missing = run('return io.read("nonexistent.md")', io=fs)
        # Both should be :error — the agent can't tell the difference
        assert r_traversal.tag_name == "error"
        assert r_missing.tag_name == "error"
