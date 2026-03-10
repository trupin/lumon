"""Tests for Lumon test blocks and assert statements."""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lumon.cli import cmd_test


@pytest.fixture
def run(runner):
    def _run(code, **kwargs):
        return runner.run(code, **kwargs)
    return _run


# ===================================================================
# Assert statement
# ===================================================================

class TestAssertStatement:
    def test_assert_true_passes(self, run):
        r = run("assert true")
        assert r.type == "result"

    def test_assert_false_fails(self, run):
        r = run("assert false")
        assert r.type == "error"
        assert "Assertion failed" in r.output.get("message", "")

    def test_assert_expression(self, run):
        r = run("assert 1 + 1 == 2")
        assert r.type == "result"

    def test_assert_expression_fails(self, run):
        r = run("assert 1 + 1 == 3")
        assert r.type == "error"

    def test_assert_with_variables(self, run):
        code = """\
let x = 42
assert x == 42"""
        r = run(code)
        assert r.type == "result"


# ===================================================================
# Test blocks
# ===================================================================

class TestTestBlock:
    def test_parse_test_block(self, run):
        """Test block is parsed and registered without error."""
        code = """\
test my.function
  assert true"""
        r = run(code)
        assert r.type == "result"

    def test_test_block_not_executed_at_registration(self, run):
        """Test blocks are registered but NOT executed during normal interpretation."""
        code = """\
test my.function
  assert false"""
        # Should NOT fail — test blocks are only registered, not run
        r = run(code)
        assert r.type == "result"

    def test_test_block_with_let_and_assert(self, run):
        code = """\
test my.function
  let x = 42
  assert x == 42"""
        r = run(code)
        assert r.type == "result"

    def test_multiple_test_blocks(self, run):
        code = """\
test my.first
  assert true

test my.second
  assert true"""
        r = run(code)
        assert r.type == "result"

    def test_test_block_with_function_call(self, run):
        code = """\
test list.ops
  let items = [1, 2, 3]
  assert list.length(items) == 3"""
        r = run(code)
        assert r.type == "result"


# ===================================================================
# Test block discovery (environment)
# ===================================================================

class TestTestBlockDiscovery:
    def test_tests_registered_in_environment(self):
        from lumon.ast_nodes import TestBlock
        from lumon.builtins import register_builtins
        from lumon.environment import Environment
        from lumon.evaluator import eval_node
        from lumon.parser import parse

        code = """\
test my.first
  assert true

test my.second
  let x = 1
  assert x == 1"""
        ast = parse(code)
        env = Environment()
        register_builtins(env, None, None)
        eval_node(ast, env)
        tests = env.get_tests()
        assert len(tests) == 2
        assert isinstance(tests[0], TestBlock)
        assert tests[0].name == "my.first"
        assert tests[1].name == "my.second"


# ===================================================================
# Source utils: test block extraction
# ===================================================================

class TestSourceUtilsTestBlocks:
    def test_extract_test_blocks(self):
        from lumon.source_utils import extract_blocks

        source = """\
test inbox.summarize
  let sample = ["a", "b"]
  assert list.length(sample) == 2

test inbox.summarize.empty
  assert true"""
        blocks = extract_blocks(source)
        assert len(blocks) == 2
        assert blocks[0][0] == "test"
        assert blocks[0][1] == "inbox.summarize"
        assert blocks[1][0] == "test"
        assert blocks[1][1] == "inbox.summarize.empty"


# ===================================================================
# Test mock builtins (mock_ask, mock_spawn, mock_plugin)
# ===================================================================

class TestMockBuiltins:
    """Tests for mock_ask, mock_spawn, and mock_plugin builtins in test runner."""

    @staticmethod
    def _run_test(
        tmp_path: Path, code: str, *, cwd: Path | None = None,
    ) -> tuple[int, str]:
        """Write a .lumon test file and run cmd_test, returning (exit_code, output).

        If *cwd* is provided, chdir there instead of tmp_path.
        The test file is always written to ``<cwd>/lumon/tests/t.lumon``.
        """
        root = cwd or tmp_path
        test_dir = root / "lumon" / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "t.lumon").write_text(code)

        args = argparse.Namespace(namespace="t")
        buf = io.StringIO()
        old_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.object(sys, "stdout", buf):
                rc = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        return rc, buf.getvalue()

    # ── mock_ask ──────────────────────────────────────────────────

    def test_mock_ask(self, tmp_path: Path) -> None:
        code = """\
define helper.greet
  "asks style then greets"
  takes:
    name: text "name"
  returns: text "greeting"

implement helper.greet
  let style = ask
    "How?"
  return style + " " + name

test mock.ask_basic
  mock_ask("Hi")
  let r = helper.greet("Bob")
  assert r == "Hi Bob"
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 0, out
        assert "PASS" in out

    def test_mock_ask_multiple(self, tmp_path: Path) -> None:
        code = """\
define helper.double
  "asks twice"
  returns: text "result"

implement helper.double
  let a = ask
    "first?"
  let b = ask
    "second?"
  return a + b

test mock.ask_multiple
  mock_ask("X")
  mock_ask("Y")
  let r = helper.double()
  assert r == "XY"
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 0, out

    def test_ask_without_mock_fails_gracefully(self, tmp_path: Path) -> None:
        """ask without mock_ask should FAIL the test, not crash the runner."""
        code = """\
define helper.prompt
  "asks a question"
  returns: text "answer"

implement helper.prompt
  let a = ask
    "question?"
  return a

test mock.ask_no_mock
  let r = helper.prompt()
  assert r == "anything"

test mock.ask_after_no_mock
  assert true
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 1, out
        assert "FAIL" in out
        assert "mock_ask" in out
        # Second test should still run and pass
        assert "PASS  mock.ask_after_no_mock" in out
        assert "1/2 passed" in out

    # ── mock_spawn ────────────────────────────────────────────────

    def test_mock_spawn(self, tmp_path: Path) -> None:
        code = """\
define helper.gather
  "gathers from sub-agents"
  returns: list "results"

implement helper.gather
  let a = spawn [{prompt: "fetch A"}]
  let b = spawn [{prompt: "fetch B"}]
  return [a, b]

test mock.spawn_basic
  mock_spawn(["ra", "rb"])
  let r = helper.gather()
  assert r == [["ra"], ["rb"]]
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 0, out
        assert "PASS" in out

    def test_mock_spawn_empty_list(self, tmp_path: Path) -> None:
        """mock_spawn([]) queues nothing — spawn returns a list of handles."""
        code = """\
define helper.one_spawn
  "spawns once"
  returns: list "result"

implement helper.one_spawn
  let a = spawn [{prompt: "fetch"}]
  return a

test mock.spawn_empty
  mock_spawn([])
  let r = helper.one_spawn()
  assert r == "should not match handle list"
"""
        rc, out = self._run_test(tmp_path, code)
        # spawn without queued response returns a list of handles, assertion fails
        assert rc == 1, out
        assert "FAIL" in out

    # ── mock_plugin ───────────────────────────────────────────────

    def test_mock_plugin(self, tmp_path: Path) -> None:
        # Layout: tmp_path/.lumon.json, tmp_path/plugins/email/*, tmp_path/sandbox/lumon/tests/*
        sandbox = tmp_path / "sandbox"
        plugin_dir = tmp_path / "plugins" / "email"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".lumon.json").write_text('{"plugins": {"email": {}}}')
        (plugin_dir / "manifest.lumon").write_text(
            'define email.send\n  "sends email"\n'
            '  takes:\n    to: text "recipient"\n  returns: text "status"\n'
        )
        (plugin_dir / "impl.lumon").write_text(
            'implement email.send\n'
            '  let r = plugin.exec("./send.sh", {to: to})\n'
            '  return r\n'
        )

        code = """\
test plugin.basic
  mock_plugin("email", "./send.sh", "ok")
  let r = email.send("a@b.com")
  assert r == "ok"
"""
        rc, out = self._run_test(tmp_path, code, cwd=sandbox)
        assert rc == 0, out
        assert "PASS" in out

    def test_mock_plugin_wrong_command(self, tmp_path: Path) -> None:
        """Calling a plugin command that wasn't mocked should fail with a clear error."""
        sandbox = tmp_path / "sandbox"
        plugin_dir = tmp_path / "plugins" / "email"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".lumon.json").write_text('{"plugins": {"email": {}}}')
        (plugin_dir / "manifest.lumon").write_text(
            'define email.send\n  "sends email"\n'
            '  takes:\n    to: text "recipient"\n  returns: text "status"\n'
        )
        (plugin_dir / "impl.lumon").write_text(
            'implement email.send\n'
            '  let r = plugin.exec("./send.sh", {to: to})\n'
            '  return r\n'
        )

        code = """\
test plugin.wrong_command
  mock_plugin("email", "./other.sh", "ok")
  let r = email.send("a@b.com")
  assert r == "ok"
"""
        rc, out = self._run_test(tmp_path, code, cwd=sandbox)
        assert rc == 1, out
        assert "FAIL" in out
        assert "No mock registered" in out

    # ── cross-test isolation ──────────────────────────────────────

    def test_mock_ask_cleared_between_tests(self, tmp_path: Path) -> None:
        """Verify that mock state is cleared between test blocks."""
        code = """\
define helper.get_answer
  "asks a question"
  returns: text "answer"

implement helper.get_answer
  let a = ask
    "question?"
  return a

test mock.ask_first
  mock_ask("yes")
  let r = helper.get_answer()
  assert r == "yes"

test mock.ask_second
  mock_ask("no")
  let r = helper.get_answer()
  assert r == "no"
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 0, out
        assert "2/2 passed" in out

    def test_unconsumed_mocks_dont_leak(self, tmp_path: Path) -> None:
        """Mocks queued but not consumed in test 1 must not leak to test 2."""
        code = """\
define helper.get_answer
  "asks a question"
  returns: text "answer"

implement helper.get_answer
  let a = ask
    "question?"
  return a

test mock.overqueue
  mock_ask("used")
  mock_ask("leftover")
  let r = helper.get_answer()
  assert r == "used"

test mock.no_leak
  mock_ask("fresh")
  let r = helper.get_answer()
  assert r == "fresh"
"""
        rc, out = self._run_test(tmp_path, code)
        assert rc == 0, out
        assert "2/2 passed" in out
