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
# io.mkdir
# ===================================================================

class TestIoMkdir:
    def test_creates_directory(self, run):
        fs = MockFS()
        r = run('return io.mkdir("newdir")', io=fs)
        assert r.tag_name == "ok"

    def test_created_dir_appears_in_list_dir(self, run):
        fs = MockFS()
        code = """
let m = io.mkdir("newdir")
return io.list_dir(".")
"""
        r = run(code, io=fs)
        assert r.tag_name == "ok"
        assert "newdir" in r.tag_value

    def test_creates_intermediate_parents(self, run):
        fs = MockFS()
        r = run('return io.mkdir("a/b/c")', io=fs)
        assert r.tag_name == "ok"

    def test_intermediate_parents_visible(self, run):
        fs = MockFS()
        code = """
let m = io.mkdir("a/b/c")
return io.list_dir("a")
"""
        r = run(code, io=fs)
        assert r.tag_name == "ok"
        assert "b" in r.tag_value

    def test_existing_dir_succeeds(self, run):
        fs = MockFS({"dir/file.md": "x"})
        r = run('return io.mkdir("dir")', io=fs)
        assert r.tag_name == "ok"

    def test_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.mkdir("../../evil")', io=fs)
        assert r.tag_name == "error"


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

    def test_list_dir_recursive(self, run):
        fs = MockFS({"dir/a.md": "a", "dir/sub/b.md": "b", "dir/sub/deep/c.md": "c"})
        r = run('return io.list_dir("dir", true)', io=fs)
        assert r.tag_name == "ok"
        assert sorted(r.tag_value) == ["a.md", "sub/b.md", "sub/deep/c.md"]

    def test_list_dir_recursive_default_false(self, run):
        fs = MockFS({"dir/a.md": "a", "dir/sub/b.md": "b"})
        r = run('return io.list_dir("dir")', io=fs)
        assert r.tag_name == "ok"
        assert sorted(r.tag_value) == ["a.md", "sub"]


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

    def test_delete_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.delete("../../evil.md")', io=fs)
        assert r.tag_name == "error"

    def test_delete_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.delete("/etc/passwd")', io=fs)
        assert r.tag_name == "error"

    def test_find_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.find("../../", "*.md")', io=fs)
        assert r.tag_name == "error"

    def test_find_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.find("/etc", "*")', io=fs)
        assert r.tag_name == "error"

    def test_grep_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.grep("../../", "secret")', io=fs)
        assert r.tag_name == "error"

    def test_grep_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.grep("/etc", "root")', io=fs)
        assert r.tag_name == "error"

    def test_head_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.head("../../etc/passwd", 5)', io=fs)
        assert r.tag_name == "error"

    def test_head_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.head("/etc/passwd", 5)', io=fs)
        assert r.tag_name == "error"

    def test_tail_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.tail("../../etc/passwd", 5)', io=fs)
        assert r.tag_name == "error"

    def test_tail_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.tail("/etc/passwd", 5)', io=fs)
        assert r.tag_name == "error"

    def test_replace_path_traversal_blocked(self, run):
        fs = MockFS()
        r = run('return io.replace("../../evil.md", "a", "b")', io=fs)
        assert r.tag_name == "error"

    def test_replace_absolute_path_blocked(self, run):
        fs = MockFS()
        r = run('return io.replace("/etc/passwd", "a", "b")', io=fs)
        assert r.tag_name == "error"

    def test_traversal_errors_indistinguishable(self, run):
        """All sandbox violations look identical to missing-file errors."""
        fs = MockFS()
        fns = [
            ('io.delete("../../x")', 'io.delete("nope")'),
            ('io.head("../../x", 1)', 'io.head("nope", 1)'),
            ('io.tail("../../x", 1)', 'io.tail("nope", 1)'),
            ('io.replace("../../x", "a", "b")', 'io.replace("nope", "a", "b")'),
        ]
        for escape_code, missing_code in fns:
            r_escape = run(f'return {escape_code}', io=fs)
            r_missing = run(f'return {missing_code}', io=fs)
            assert r_escape.tag_name == "error"
            assert r_missing.tag_name == "error"


# ===================================================================
# io.delete
# ===================================================================

class TestIoDelete:
    def test_delete_existing(self, run):
        fs = MockFS({"file.md": "content"})
        r = run('return io.delete("file.md")', io=fs)
        assert r.tag_name == "ok"

    def test_delete_missing(self, run):
        fs = MockFS()
        r = run('return io.delete("missing.md")', io=fs)
        assert r.tag_name == "error"

    def test_write_then_delete_then_read(self, run):
        fs = MockFS({"file.md": "content"})
        r = run(
            'let d = io.delete("file.md")\n'
            'return io.read("file.md")',
            io=fs,
        )
        assert r.tag_name == "error"


class TestIoDeleteDir:
    def test_delete_dir_existing(self, run):
        fs = MockFS({"tmp/a.txt": "a", "tmp/b.txt": "b"})
        r = run('return io.delete_dir("tmp")', io=fs)
        assert r.tag_name == "ok"

    def test_delete_dir_then_list(self, run):
        fs = MockFS({"tmp/a.txt": "a", "tmp/sub/b.txt": "b", "keep.txt": "keep"})
        r = run(
            'let d = io.delete_dir("tmp")\n'
            'return io.list_dir(".")',
            io=fs,
        )
        assert r.tag_name == "ok"
        assert "tmp" not in r.tag_value
        assert "keep.txt" in r.tag_value

    def test_delete_dir_missing(self, run):
        fs = MockFS()
        r = run('return io.delete_dir("nonexistent")', io=fs)
        assert r.tag_name == "error"

    def test_delete_dir_root_blocked(self, run):
        fs = MockFS({"a.txt": "a"})
        r = run('return io.delete_dir(".")', io=fs)
        assert r.tag_name == "error"


# ===================================================================
# io.find
# ===================================================================

class TestIoFind:
    def test_find_by_pattern(self, run):
        fs = MockFS({"a.md": "a", "b.txt": "b", "c.md": "c"})
        r = run('return io.find(".", "*.md")', io=fs)
        assert r.tag_name == "ok"
        assert sorted(r.tag_value) == ["a.md", "c.md"]

    def test_find_no_matches(self, run):
        fs = MockFS({"a.txt": "a"})
        r = run('return io.find(".", "*.md")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == []

    def test_find_nested_dirs(self, run):
        fs = MockFS({"dir/sub/file.md": "x", "dir/other.txt": "y"})
        r = run('return io.find("dir", "*.md")', io=fs)
        assert r.tag_name == "ok"
        assert "sub/file.md" in r.tag_value


# ===================================================================
# io.grep
# ===================================================================

class TestIoGrep:
    def test_grep_match_found(self, run):
        fs = MockFS({"file.md": "hello world\ngoodbye"})
        r = run('return io.grep(".", "hello")', io=fs)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 1
        assert "hello" in r.tag_value[0]
        assert ":1:" in r.tag_value[0]

    def test_grep_no_match(self, run):
        fs = MockFS({"file.md": "hello world"})
        r = run('return io.grep(".", "xyz")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == []

    def test_grep_multi_file(self, run):
        fs = MockFS({"a.md": "foo bar", "b.md": "baz foo"})
        r = run('return io.grep(".", "foo")', io=fs)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 2


# ===================================================================
# io.head
# ===================================================================

class TestIoHead:
    def test_head_first_3_lines(self, run):
        fs = MockFS({"file.md": "a\nb\nc\nd\ne"})
        r = run('return io.head("file.md", 3)', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "a\nb\nc"

    def test_head_n_larger_than_file(self, run):
        fs = MockFS({"file.md": "a\nb"})
        r = run('return io.head("file.md", 10)', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "a\nb"

    def test_head_empty_file(self, run):
        fs = MockFS({"file.md": ""})
        r = run('return io.head("file.md", 3)', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == ""

    def test_head_missing_file(self, run):
        fs = MockFS()
        r = run('return io.head("missing.md", 3)', io=fs)
        assert r.tag_name == "error"


# ===================================================================
# io.tail
# ===================================================================

class TestIoTail:
    def test_tail_last_3_lines(self, run):
        fs = MockFS({"file.md": "a\nb\nc\nd\ne"})
        r = run('return io.tail("file.md", 3)', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "c\nd\ne"

    def test_tail_n_larger_than_file(self, run):
        fs = MockFS({"file.md": "a\nb"})
        r = run('return io.tail("file.md", 10)', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == "a\nb"

    def test_tail_missing_file(self, run):
        fs = MockFS()
        r = run('return io.tail("missing.md", 3)', io=fs)
        assert r.tag_name == "error"


# ===================================================================
# io.replace
# ===================================================================

class TestIoReplace:
    def test_replace_all_occurrences(self, run):
        fs = MockFS({"file.md": "foo bar foo"})
        r = run('return io.replace("file.md", "foo", "baz")', io=fs)
        assert r.tag_name == "ok"
        assert fs.read("file.md") == {"tag": "ok", "value": "baz bar baz"}

    def test_replace_no_match_still_ok(self, run):
        fs = MockFS({"file.md": "hello"})
        r = run('return io.replace("file.md", "xyz", "abc")', io=fs)
        assert r.tag_name == "ok"
        assert fs.read("file.md") == {"tag": "ok", "value": "hello"}

    def test_replace_missing_file(self, run):
        fs = MockFS()
        r = run('return io.replace("missing.md", "a", "b")', io=fs)
        assert r.tag_name == "error"
