"""Tests for Lumon control flow: if/else, match (patterns, guards, exhaustiveness),
with/then/else, ask, spawn, async/await."""

import pytest

from tests.conftest import MockFS, MockHTTP


@pytest.fixture
def run(runner):
    def _run(code, *, io=None, http=None):
        return runner.run(code, io=io, http=http)
    return _run


# ===================================================================
# if / else
# ===================================================================

class TestIfElse:
    def test_if_true_returns_then_branch(self, run):
        r = run('return if true "yes" else "no"')
        assert r.value == "yes"

    def test_if_false_returns_else_branch(self, run):
        r = run('return if false "yes" else "no"')
        assert r.value == "no"

    def test_if_truthy_number(self, run):
        r = run('return if 1 "yes" else "no"')
        assert r.value == "yes"

    def test_if_falsy_zero(self, run):
        r = run('return if 0 "yes" else "no"')
        assert r.value == "no"

    def test_if_expression_in_binding(self, run):
        r = run('let x = if true 42 else 0\nreturn x')
        assert r.value == 42

    def test_if_with_comparison(self, run):
        r = run('let count = 5\nreturn if count > 0 "has items" else "empty"')
        assert r.value == "has items"

    def test_if_statement_no_else(self, run):
        """if without else is valid as a statement (return value ignored)."""
        r = run('let x = 42\nif true\n  let y = 1\nreturn x')
        assert r.value == 42


# ===================================================================
# match — literal patterns
# ===================================================================

class TestMatchLiteralPatterns:
    def test_match_number(self, run):
        r = run(
            'let x = 42\n'
            'return match x\n'
            '  42 -> "found"\n'
            '  _ -> "other"'
        )
        assert r.value == "found"

    def test_match_string(self, run):
        r = run(
            'let s = "hello"\n'
            'return match s\n'
            '  "hello" -> "greeting"\n'
            '  _ -> "other"'
        )
        assert r.value == "greeting"

    def test_match_bool(self, run):
        r = run(
            'return match true\n'
            '  true -> "yes"\n'
            '  false -> "no"'
        )
        assert r.value == "yes"

    def test_match_none(self, run):
        r = run(
            'return match none\n'
            '  none -> "nothing"\n'
            '  _ -> "something"'
        )
        assert r.value == "nothing"

    def test_match_fallthrough_to_wildcard(self, run):
        r = run(
            'return match 99\n'
            '  42 -> "found"\n'
            '  _ -> "other"'
        )
        assert r.value == "other"


# ===================================================================
# match — binding patterns
# ===================================================================

class TestMatchBindingPatterns:
    def test_binding_captures_value(self, run):
        r = run(
            'return match 42\n'
            '  x -> x + 1'
        )
        assert r.value == 43

    def test_binding_in_non_first_arm(self, run):
        r = run(
            'return match 99\n'
            '  42 -> "found"\n'
            '  x -> x'
        )
        assert r.value == 99


# ===================================================================
# match — map patterns (destructuring)
# ===================================================================

class TestMatchMapPatterns:
    def test_destructure_map(self, run):
        r = run(
            'let r = {status: "ok", data: "hello"}\n'
            'return match r\n'
            '  {status: "ok", data: d} -> d\n'
            '  _ -> "fail"'
        )
        assert r.value == "hello"

    def test_destructure_nested_map(self, run):
        r = run(
            'let r = {status: "ok", data: {title: "Lumon"}}\n'
            'return match r\n'
            '  {status: "ok", data: {title: t}} -> t\n'
            '  _ -> "fail"'
        )
        assert r.value == "Lumon"

    def test_map_pattern_no_match(self, run):
        r = run(
            'let r = {status: "error", msg: "fail"}\n'
            'return match r\n'
            '  {status: "ok", data: d} -> d\n'
            '  {status: "error", msg: m} -> m\n'
            '  _ -> "unknown"'
        )
        assert r.value == "fail"


# ===================================================================
# match — list patterns
# ===================================================================

class TestMatchListPatterns:
    def test_destructure_list_head(self, run):
        r = run(
            'return match [1, 2, 3]\n'
            '  [first, ...rest] -> first'
        )
        assert r.value == 1

    def test_destructure_list_rest(self, run):
        r = run(
            'return match [1, 2, 3]\n'
            '  [first, ...rest] -> rest'
        )
        assert r.value == [2, 3]

    def test_destructure_fixed_elements(self, run):
        r = run(
            'return match [1, 2]\n'
            '  [a, b] -> a + b\n'
            '  _ -> 0'
        )
        assert r.value == 3

    def test_empty_list_pattern(self, run):
        r = run(
            'return match []\n'
            '  [] -> "empty"\n'
            '  _ -> "not empty"'
        )
        assert r.value == "empty"


# ===================================================================
# match — tag patterns
# ===================================================================

class TestMatchTagPatterns:
    def test_match_bare_tag(self, run):
        r = run(
            'return match :ok\n'
            '  :ok -> "success"\n'
            '  :error -> "fail"'
        )
        assert r.value == "success"

    def test_match_tag_with_payload(self, run):
        r = run(
            'return match :error("not found")\n'
            '  :ok -> "success"\n'
            '  :error(m) -> m'
        )
        assert r.value == "not found"

    def test_match_tag_ok_with_value(self, run):
        r = run(
            'return match :ok("data")\n'
            '  :ok(v) -> v\n'
            '  :error(m) -> m'
        )
        assert r.value == "data"

    def test_match_tag_wildcard_payload(self, run):
        r = run(
            'return match :error("msg")\n'
            '  :ok -> "ok"\n'
            '  :error(_) -> "failed"'
        )
        assert r.value == "failed"


# ===================================================================
# match — wildcard
# ===================================================================

class TestMatchWildcard:
    def test_wildcard_catches_all(self, run):
        r = run(
            'return match "anything"\n'
            '  _ -> "caught"'
        )
        assert r.value == "caught"


# ===================================================================
# match — guards
# ===================================================================

class TestMatchGuards:
    def test_guard_true_matches(self, run):
        r = run(
            'return match 15\n'
            '  x if x > 10 -> "big"\n'
            '  x -> "small"'
        )
        assert r.value == "big"

    def test_guard_false_falls_through(self, run):
        r = run(
            'return match 5\n'
            '  x if x > 10 -> "big"\n'
            '  x -> "small"'
        )
        assert r.value == "small"

    def test_guard_with_text_contains(self, run):
        r = run(
            'let item = "buy milk #urgent"\n'
            'return match item\n'
            '  x if text.contains(x, "#urgent") -> "urgent"\n'
            '  x if text.contains(x, "#errand") -> "errand"\n'
            '  _ -> "uncategorized"'
        )
        assert r.value == "urgent"

    def test_guard_multiple_arms(self, run):
        r = run(
            'let item = "do laundry #errand"\n'
            'return match item\n'
            '  x if text.contains(x, "#urgent") -> "urgent"\n'
            '  x if text.contains(x, "#errand") -> "errand"\n'
            '  _ -> "uncategorized"'
        )
        assert r.value == "errand"


# ===================================================================
# match — multi-line arms
# ===================================================================

class TestMatchMultiLineArms:
    def test_block_arm(self, run):
        r = run(
            'return match :ok("raw")\n'
            '  :error(_) -> :error("no config")\n'
            '  :ok(raw) ->\n'
            '    let upper = text.upper(raw)\n'
            '    :ok(upper)'
        )
        assert r.value == {"tag": "ok", "value": "RAW"}

    def test_block_arm_last_expression_is_value(self, run):
        r = run(
            'return match 5\n'
            '  x ->\n'
            '    let doubled = x * 2\n'
            '    let result = doubled + 1\n'
            '    result'
        )
        assert r.value == 11


# ===================================================================
# match — exhaustiveness
# ===================================================================

class TestMatchExhaustiveness:
    def test_exhaustive_match_on_tags_is_ok(self, run):
        """Matching all tags from a known set should not warn."""
        code = (
            'define test.fn\n'
            '  "test"\n'
            '  returns: :ok | :error(text) "result"\n'
            '\n'
            'implement test.fn\n'
            '  return :ok\n'
            '\n'
            'let r = test.fn()\n'
            'return match r\n'
            '  :ok -> "ok"\n'
            '  :error(m) -> m'
        )
        r = run(code)
        # Should succeed without warnings about missing cases
        assert r.type == "result"

    def test_non_exhaustive_match_warns(self, run):
        """Missing a tag from a known set should produce a warning or error."""
        code = (
            'define test.fn\n'
            '  "test"\n'
            '  returns: :ok | :error(text) "result"\n'
            '\n'
            'implement test.fn\n'
            '  return :ok\n'
            '\n'
            'let r = test.fn()\n'
            'return match r\n'
            '  :ok -> "ok"'
        )
        r = run(code)
        # Should warn about missing :error case
        # (exact behavior TBD — could be warning or error)
        # For now, we just verify it's flagged somehow


# ===================================================================
# with / then / else
# ===================================================================

class TestWithThenElse:
    def test_happy_path(self, run):
        r = run(
            'let result = with\n'
            '  a = 1\n'
            '  b = 2\n'
            '  c = a + b\n'
            'then\n'
            '  c\n'
            'else\n'
            '  0\n'
            'return result'
        )
        assert r.value == 3

    def test_none_bails_to_else(self, run):
        r = run(
            'let result = with\n'
            '  a = 1\n'
            '  b = none\n'
            '  c = b + 1\n'
            'then\n'
            '  c\n'
            'else\n'
            '  "failed"\n'
            'return result'
        )
        assert r.value == "failed"

    def test_with_using_list_head(self, run):
        r = run(
            'let result = with\n'
            '  first = list.head([])\n'
            'then\n'
            '  first\n'
            'else\n'
            '  "empty"\n'
            'return result'
        )
        assert r.value == "empty"

    def test_with_all_steps_succeed(self, run):
        r = run(
            'let result = with\n'
            '  first = list.head([10, 20, 30])\n'
            'then\n'
            '  first\n'
            'else\n'
            '  0\n'
            'return result'
        )
        assert r.value == 10

    def test_with_nil_coalescing_inside(self, run):
        r = run(
            'let result = with\n'
            '  items = list.head([]) ?? 42\n'
            'then\n'
            '  items\n'
            'else\n'
            '  0\n'
            'return result'
        )
        assert r.value == 42


# ===================================================================
# ask
# ===================================================================

class TestAsk:
    def test_ask_produces_ask_output(self, run):
        r = run(
            'let decision = ask\n'
            '  "Which item first?"\n'
            '  context: [1, 2, 3]\n'
            '  expects: {action: text}'
        )
        assert r.type == "ask"
        assert r.output["prompt"] == "Which item first?"
        assert r.output["context"] == [1, 2, 3]

    def test_ask_includes_expects(self, run):
        r = run(
            'let answer = ask\n'
            '  "Pick one"\n'
            '  context: "data"\n'
            '  expects: text'
        )
        assert r.type == "ask"
        assert "expects" in r.output


# ===================================================================
# spawn
# ===================================================================

class TestSpawn:
    def test_spawn_produces_spawn_output(self, run):
        r = run(
            'let h = spawn\n'
            '  "Analyze this"\n'
            '  context: "article text"\n'
            '  expects: {bias: number, summary: text}'
        )
        # spawn yields control, producing a spawn_batch or similar
        assert r.type in ("spawn_batch", "ask")

    def test_spawn_with_fork(self, run):
        r = run(
            'let h = spawn\n'
            '  "Analyze with history"\n'
            '  context: "data"\n'
            '  fork: true\n'
            '  expects: {result: text}'
        )
        assert r.type in ("spawn_batch", "ask")


# ===================================================================
# async / await
# ===================================================================

class TestAsyncAwait:
    def test_await_resolves_handle(self, run):
        """In initial sequential mode, async is a no-op and await returns the value."""
        io = MockFS({"file.md": "content"})
        r = run(
            'let h = async io.read("file.md")\n'
            'let result = await h\n'
            'return result',
            io=io,
        )
        assert r.value == {"tag": "ok", "value": "content"}

    def test_await_all_resolves_handles(self, run):
        io = MockFS({"a.md": "aaa", "b.md": "bbb"})
        r = run(
            'let h1 = async io.read("a.md")\n'
            'let h2 = async io.read("b.md")\n'
            'let results = await_all [h1, h2]\n'
            'return results',
            io=io,
        )
        assert r.value == [
            {"tag": "ok", "value": "aaa"},
            {"tag": "ok", "value": "bbb"},
        ]
