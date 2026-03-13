"""Tests for Lumon error model: interpreter errors (structured JSON, halts)
and recoverable errors (tag returns, execution continues)."""

import pytest

from tests.conftest import MockFS


@pytest.fixture
def run(runner):
    def _run(code, **kwargs):
        return runner.run(code, **kwargs)
    return _run


# ===================================================================
# Interpreter errors (execution halts)
# ===================================================================

class TestInterpreterErrors:
    def test_undefined_variable(self, run):
        r = run("return x")
        assert r.type == "error"
        assert "message" in r.error
        assert "x" in r.error["message"].lower() or "undefined" in r.error["message"].lower()

    def test_division_by_zero(self, run):
        r = run("return 1 / 0")
        assert r.type == "error"
        assert "message" in r.error

    def test_recursion_depth_exceeded(self, run):
        r = run(
            'define inf.loop\n'
            '  "Infinite"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "never"\n'
            '\n'
            'implement inf.loop\n'
            '  return inf.loop(n + 1)\n'
            '\n'
            'return inf.loop(0)'
        )
        assert r.type == "error"

    def test_error_includes_message(self, run):
        r = run("return undefined_var")
        assert r.type == "error"
        assert "message" in r.error

    def test_error_includes_trace(self, run):
        """Interpreter errors should include a trace field."""
        r = run(
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: number "n"\n'
            '\n'
            'implement demo.fn\n'
            '  return undefined_var\n'
            '\n'
            'return demo.fn()'
        )
        assert r.type == "error"
        assert "trace" in r.error

    def test_error_includes_function(self, run):
        r = run(
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: number "n"\n'
            '\n'
            'implement demo.fn\n'
            '  return undefined_var\n'
            '\n'
            'return demo.fn()'
        )
        assert r.type == "error"
        assert "function" in r.error
        assert r.error["function"] == "demo.fn"


# ===================================================================
# Recoverable errors (tag returns, execution continues)
# ===================================================================

class TestRecoverableErrors:
    def test_io_read_missing_returns_error_tag(self, run):
        fs = MockFS()
        r = run('return io.read("missing.md")', io=fs)
        assert r.type == "result"  # Not an interpreter error
        assert r.tag_name == "error"

    def test_io_read_error_then_continue(self, run):
        """Program continues after a recoverable error."""
        fs = MockFS()
        r = run(
            'let result = io.read("missing.md")\n'
            'let msg = match result\n'
            '  :ok(content) -> content\n'
            '  :error(m) -> "handled: " + m\n'
            'return msg',
            io=fs,
        )
        assert r.type == "result"
        assert r.value.startswith("handled:")

    def test_multiple_recoverable_errors(self, run):
        """Multiple io operations can fail and be handled without halting."""
        fs = MockFS({"exists.md": "content"})
        r = run(
            'let r1 = io.read("missing1.md")\n'
            'let r2 = io.read("missing2.md")\n'
            'let r3 = io.read("exists.md")\n'
            'let results = [r1, r2, r3]\n'
            'return results',
            io=fs,
        )
        assert r.type == "result"
        assert r.value[0]["tag"] == "error"
        assert r.value[1]["tag"] == "error"
        assert r.value[2]["tag"] == "ok"


# ===================================================================
# Output protocol envelopes
# ===================================================================

class TestOutputProtocol:
    def test_success_envelope(self, run):
        r = run('return 42')
        assert r.output == {"type": "result", "value": 42}

    def test_success_envelope_text(self, run):
        r = run('return "hello"')
        assert r.output == {"type": "result", "value": "hello"}

    def test_success_envelope_list(self, run):
        r = run('return [1, 2, 3]')
        assert r.output == {"type": "result", "value": [1, 2, 3]}

    def test_error_envelope_structure(self, run):
        r = run('return undefined_var')
        assert r.output["type"] == "error"
        assert "message" in r.output

    def test_ask_envelope(self, run):
        r = run(
            'let x = ask\n'
            '  "What to do?"\n'
            '  context: "data"\n'
            '  expects: text'
        )
        assert r.output["type"] == "ask"
        assert r.output["prompt"] == "What to do?"
        assert "context" in r.output
        assert "expects" in r.output

    def test_tag_result_envelope(self, run):
        r = run('return :ok("done")')
        assert r.output == {
            "type": "result",
            "value": {"tag": "ok", "value": "done"},
        }


# ===================================================================
# Type name in error messages
# ===================================================================


class TestTypeNameErrors:
    def test_add_bool_to_number(self, run):
        r = run("return true + 1")
        assert r.type == "error"

    def test_field_on_list(self, run):
        r = run("let xs = [1, 2]\nreturn xs.first")
        assert r.type == "result"
        assert r.value is None

    def test_field_on_tag(self, run):
        r = run("let t = :ok\nreturn t.name")
        assert r.type == "result"
        assert r.value is None

    def test_index_on_map(self, run):
        r = run("let m = {a: 1}\nreturn m[0]")
        assert r.type == "error"
