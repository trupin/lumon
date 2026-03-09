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


# ===================================================================
# git.init
# ===================================================================

class TestGitInit:
    def test_returns_ok(self, run):
        git = MockGit()
        r = run('return git.init()', git=git)
        assert r.tag_name == "ok"


# ===================================================================
# git.add
# ===================================================================

class TestGitAdd:
    def test_stages_file(self, run):
        git = MockGit()
        r = run('return git.add("file.py")', git=git)
        assert r.tag_name == "ok"
        assert "file.py" in git._staged


# ===================================================================
# git.commit
# ===================================================================

class TestGitCommit:
    def test_creates_commit(self, run):
        git = MockGit()
        git._staged = ["file.py"]
        r = run('return git.commit("initial commit")', git=git)
        assert r.tag_name == "ok"
        assert isinstance(r.tag_value, str)
        assert len(r.tag_value) > 0

    def test_clears_staged(self, run):
        git = MockGit()
        git._staged = ["file.py"]
        run('return git.commit("msg")', git=git)
        assert git._staged == []

    def test_error_nothing_staged(self, run):
        git = MockGit()
        r = run('return git.commit("msg")', git=git)
        assert r.tag_name == "error"

    def test_adds_to_log(self, run):
        git = MockGit()
        git._staged = ["file.py"]
        run('return git.commit("first")', git=git)
        assert len(git._log) == 1
        assert "first" in git._log[0]


# ===================================================================
# git.diff
# ===================================================================

class TestGitDiff:
    def test_returns_diff_text(self, run):
        git = MockGit()
        git._diff = "--- a/file.py\n+++ b/file.py\n"
        r = run('return git.diff()', git=git)
        assert r.tag_name == "ok"
        assert "file.py" in r.tag_value

    def test_empty_diff(self, run):
        git = MockGit()
        r = run('return git.diff()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == ""


# ===================================================================
# git.diff_staged
# ===================================================================

class TestGitDiffStaged:
    def test_returns_staged_diff(self, run):
        git = MockGit()
        git._diff_staged = "+new line"
        r = run('return git.diff_staged()', git=git)
        assert r.tag_name == "ok"
        assert "+new line" in r.tag_value

    def test_empty_staged_diff(self, run):
        git = MockGit()
        r = run('return git.diff_staged()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == ""


# ===================================================================
# git.branch
# ===================================================================

class TestGitBranch:
    def test_creates_branch(self, run):
        git = MockGit()
        r = run('return git.branch("feature")', git=git)
        assert r.tag_name == "ok"
        assert "feature" in git._branches

    def test_duplicate_branch_errors(self, run):
        git = MockGit(branches=["main", "feature"])
        r = run('return git.branch("feature")', git=git)
        assert r.tag_name == "error"


# ===================================================================
# git.branch_list
# ===================================================================

class TestGitBranchList:
    def test_lists_branches(self, run):
        git = MockGit(branches=["main", "dev"])
        r = run('return git.branch_list()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == ["main", "dev"]

    def test_empty_branches(self, run):
        git = MockGit()
        r = run('return git.branch_list()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == []


# ===================================================================
# git.checkout
# ===================================================================

class TestGitCheckout:
    def test_switches_branch(self, run):
        git = MockGit(branches=["main", "feature"])
        r = run('return git.checkout("feature")', git=git)
        assert r.tag_name == "ok"
        assert git._current_branch == "feature"

    def test_unknown_ref_errors(self, run):
        git = MockGit(branches=["main"])
        r = run('return git.checkout("nonexistent")', git=git)
        assert r.tag_name == "error"


# ===================================================================
# git.reset
# ===================================================================

class TestGitReset:
    def test_unstages_file(self, run):
        git = MockGit()
        git._staged = ["file.py", "other.py"]
        r = run('return git.reset("file.py")', git=git)
        assert r.tag_name == "ok"
        assert "file.py" not in git._staged
        assert "other.py" in git._staged

    def test_reset_unstaged_file_ok(self, run):
        git = MockGit()
        r = run('return git.reset("file.py")', git=git)
        assert r.tag_name == "ok"


# ===================================================================
# git.show
# ===================================================================

class TestGitShow:
    def test_shows_commit(self, run):
        git = MockGit(log_entries=["abc123 First commit"])
        git._show["HEAD"] = "commit abc123\nAuthor: Test\n\n    First commit"
        r = run('return git.show("HEAD")', git=git)
        assert r.tag_name == "ok"
        assert "abc123" in r.tag_value

    def test_bad_ref_errors(self, run):
        git = MockGit()
        r = run('return git.show("nonexistent")', git=git)
        assert r.tag_name == "error"


# ===================================================================
# git.tag
# ===================================================================

class TestGitTag:
    def test_creates_tag(self, run):
        git = MockGit()
        r = run('return git.tag("v1.0")', git=git)
        assert r.tag_name == "ok"
        assert "v1.0" in git._tags

    def test_duplicate_tag_errors(self, run):
        git = MockGit(tags=["v1.0"])
        r = run('return git.tag("v1.0")', git=git)
        assert r.tag_name == "error"


# ===================================================================
# git.tag_list
# ===================================================================

class TestGitTagList:
    def test_lists_tags(self, run):
        git = MockGit(tags=["v1.0", "v2.0"])
        r = run('return git.tag_list()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == ["v1.0", "v2.0"]

    def test_empty_tags(self, run):
        git = MockGit()
        r = run('return git.tag_list()', git=git)
        assert r.tag_name == "ok"
        assert r.tag_value == []


# ===================================================================
# Integration: full workflow
# ===================================================================

class TestGitWorkflow:
    def test_add_commit_log(self, run):
        """Agent can add, commit, then see the commit in log."""
        git = MockGit()
        code = """
let a = git.add("main.lumon")
let c = git.commit("implement greet")
return git.log(1)
"""
        r = run(code, git=git)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 1
        assert "implement greet" in r.tag_value[0]

    def test_init_add_commit_workflow(self, run):
        """Agent can init, add, commit, then see the commit in log."""
        git = MockGit()
        code = """
let i = git.init()
let a = git.add("main.lumon")
let c = git.commit("initial setup")
return git.log(1)
"""
        r = run(code, git=git)
        assert r.tag_name == "ok"
        assert len(r.tag_value) == 1
        assert "initial setup" in r.tag_value[0]

    def test_branch_checkout_workflow(self, run):
        """Agent can create and switch branches."""
        git = MockGit(branches=["main"])
        code = """
let b = git.branch("feature/new")
let co = git.checkout("feature/new")
return git.branch_list()
"""
        r = run(code, git=git)
        assert r.tag_name == "ok"
        assert "main" in r.tag_value
        assert "feature/new" in r.tag_value
