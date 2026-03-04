"""Tests for Lumon git.* built-ins with MockGit."""

import pytest

from tests.conftest import MockGit


@pytest.fixture
def run(runner):
    def _run(code, *, git=None):
        return runner.run(code, git=git)
    return _run


# ===================================================================
# git.status
# ===================================================================

class TestGitStatus:
    def test_returns_status_text(self, run):
        git = MockGit(status_output="M  file.py\n?? new.txt\n")
        r = run('return git.status()', git=git)
        assert r.tag_name == "ok"
        assert "file.py" in r.tag_value

    def test_empty_status(self, run):
        git = MockGit(status_output="")
        r = run('return git.status()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == ""


# ===================================================================
# git.log
# ===================================================================

class TestGitLog:
    def test_returns_log_entries(self, run):
        git = MockGit(log_entries=["abc123 First commit", "def456 Second commit"])
        r = run('return git.log(2)', git=git)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 2
        assert "abc123" in r.tag_value[0]

    def test_respects_n_limit(self, run):
        git = MockGit(log_entries=["a First", "b Second", "c Third"])
        r = run('return git.log(1)', git=git)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 1
