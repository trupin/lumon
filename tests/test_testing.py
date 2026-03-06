"""Tests for Lumon test blocks and assert statements."""

import pytest


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
