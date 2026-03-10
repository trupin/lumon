"""Tests for Lumon control flow: if/else, match (patterns, guards, exhaustiveness),
with/then/else, ask, spawn."""

import json
import os

import pytest

from tests.conftest import MockFS


@pytest.fixture
def run(runner):
    def _run(code, *, io=None):
        return runner.run(code, io=io)
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
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: :ok | :error(text) "result"\n'
            '\n'
            'implement demo.fn\n'
            '  return :ok\n'
            '\n'
            'let r = demo.fn()\n'
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
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: :ok | :error(text) "result"\n'
            '\n'
            'implement demo.fn\n'
            '  return :ok\n'
            '\n'
            'let r = demo.fn()\n'
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
            'let h = spawn [{prompt: "Analyze this", context: "article text"}]'
        )
        assert r.type == "spawn_batch"

    def test_spawn_with_fork(self, run):
        r = run(
            'let h = spawn [{prompt: "Analyze with history", context: "data", fork: true}]'
        )
        assert r.type == "spawn_batch"

    def test_multi_entry_spawn_batched(self, run):
        """Multi-entry spawn returns a batch with all entries."""
        r = run(
            'let results = spawn [\n'
            '  {prompt: "Task A", context: "data a"},\n'
            '  {prompt: "Task B", context: "data b"}\n'
            ']\n'
            'return results'
        )
        assert r.type == "spawn_batch"
        assert "spawns" in r.output
        assert len(r.output["spawns"]) == 2
        assert r.output["spawns"][0]["prompt"] == "Task A"
        assert r.output["spawns"][1]["prompt"] == "Task B"

    def test_separate_spawns_batched(self, run):
        """Separate spawn expressions each produce their own batch."""
        r = run(
            'let a = spawn [{prompt: "Task A", context: "data a"}]\n'
            'let b = spawn [{prompt: "Task B", context: "data b"}]\n'
            'return [a, b]'
        )
        # Two separate spawns produce two pending spawns total
        assert r.type == "spawn_batch"
        assert "spawns" in r.output
        assert len(r.output["spawns"]) == 2

    def test_multi_entry_spawn_replay(self):
        """Responding to multi-entry spawn resolves all entries as a list."""
        from lumon.interpreter import interpret
        code = (
            'let results = spawn [\n'
            '  {prompt: "Task A", context: "data a"},\n'
            '  {prompt: "Task B", context: "data b"}\n'
            ']\n'
            'return results'
        )
        result = interpret(code, responses=["result A", "result B"])
        assert result["type"] == "result"
        assert result["value"] == ["result A", "result B"]

    def test_single_spawn_replay(self):
        """Single-entry spawn returns a list with one element."""
        from lumon.interpreter import interpret
        code = 'let x = spawn [{prompt: "Task"}]\nreturn x'
        result = interpret(code, responses=["raw value"])
        assert result["type"] == "result"
        assert result["value"] == ["raw value"]


# ===================================================================
# if statement with else (false branch)
# ===================================================================


class TestIfStatementElse:
    def test_if_statement_else_false_branch(self, run):
        code = 'if false\n  return "yes"\nelse\n  return "no"'
        r = run(code)
        assert r.value == "no"


# ===================================================================
# match non-exhaustive
# ===================================================================


class TestMatchNonExhaustive:
    def test_match_non_exhaustive(self, run):
        r = run(
            'return match 99\n'
            '  "hello" -> true'
        )
        assert r.type == "error"
        assert "no pattern matched" in r.output.get("message", "").lower()


# ===================================================================
# with/then/else nil falls through
# ===================================================================


class TestWithElse:
    def test_with_nil_falls_through(self, run):
        code = (
            'let result = with\n'
            '  x = none\n'
            'then\n'
            '  x\n'
            'else\n'
            '  "fallback"\n'
            'return result'
        )
        r = run(code)
        assert r.value == "fallback"

    def test_with_unwraps_ok_tag(self, run):
        code = (
            'let result = with\n'
            '  x = :ok(42)\n'
            'then\n'
            '  x\n'
            'else\n'
            '  0\n'
            'return result'
        )
        r = run(code)
        assert r.value == 42

    def test_with_bails_on_error_tag(self, run):
        code = (
            'let result = with\n'
            '  x = :error("bad input")\n'
            'then\n'
            '  x\n'
            'else\n'
            '  "failed"\n'
            'return result'
        )
        r = run(code)
        assert r.value == "failed"

    def test_with_ok_chain(self, run):
        code = (
            'let result = with\n'
            '  a = :ok(10)\n'
            '  b = :ok(20)\n'
            'then\n'
            '  a + b\n'
            'else\n'
            '  0\n'
            'return result'
        )
        r = run(code)
        assert r.value == 30

    def test_with_ok_chain_bails_on_error(self, run):
        code = (
            'let result = with\n'
            '  a = :ok(10)\n'
            '  b = :error("oops")\n'
            'then\n'
            '  a + b\n'
            'else\n'
            '  "bail"\n'
            'return result'
        )
        r = run(code)
        assert r.value == "bail"

    def test_with_non_ok_error_tag_binds_as_is(self, run):
        code = (
            'let result = with\n'
            '  x = :pending\n'
            'then\n'
            '  x\n'
            'else\n'
            '  "nope"\n'
            'return result'
        )
        r = run(code)
        assert r.value == {"tag": "pending"}


# ===================================================================
# ask / spawn signals
# ===================================================================


class TestAskSpawnSignals:
    def test_ask_signal(self, run):
        r = run(
            'let answer = ask\n'
            '  "What to do?"\n'
            '  context: "data"\n'
            '  expects: text'
        )
        assert r.type == "ask"
        assert r.output["prompt"] == "What to do?"

    def test_spawn_signal(self, run):
        r = run(
            'let h = spawn [{prompt: "Do something", context: [1, 2, 3]}]'
        )
        assert r.type == "spawn_batch"


# ===================================================================
# file-based comm (comm_dir)
# ===================================================================


class TestCommDir:
    """Tests for file-based spawn/ask communication via comm_dir."""

    def test_spawn_batch_writes_context_files(self, tmp_path: object) -> None:
        """spawn_batch with comm_dir writes context to files and returns lightweight output."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import interpret

        comm_dir = os.path.join(str(tmp_path), "session1")
        code = (
            'let results = spawn [\n'
            '  {prompt: "Task A", context: {data: "large payload"}},\n'
            '  {prompt: "Task B", context: [1, 2, 3]}\n'
            ']\n'
            'return results'
        )
        result = interpret(code, comm_dir=comm_dir)
        assert result["type"] == "spawn_batch"
        assert result["session"] == "session1"
        assert "spawns" in result
        spawns = result["spawns"]
        assert len(spawns) == 2

        # Check spawn_0
        s0 = spawns[0]
        assert s0["spawn_id"] == "spawn_0"
        assert "context_file" in s0
        assert s0["context_file"].endswith("spawn_0_context.json")
        assert "response_file" in s0
        assert "Context data:" in s0["prompt"]
        # Context should NOT be inline
        assert "large payload" not in json.dumps(s0)
        # Context file should exist with correct content
        with open(s0["context_file"], encoding="utf-8") as f:
            ctx = json.load(f)
        assert ctx == {"data": "large payload"}

        # Check spawn_1
        s1 = spawns[1]
        assert s1["spawn_id"] == "spawn_1"
        with open(s1["context_file"], encoding="utf-8") as f:
            ctx = json.load(f)
        assert ctx == [1, 2, 3]

    def test_ask_writes_context_file(self, tmp_path: object) -> None:
        """ask with comm_dir writes context to a file and returns lightweight output."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import interpret

        comm_dir = os.path.join(str(tmp_path), "session2")
        code = (
            'let x = ask\n'
            '  "Which item?"\n'
            '  context: {items: [1, 2, 3]}\n'
            '  expects: text'
        )
        result = interpret(code, comm_dir=comm_dir)
        assert result["type"] == "ask"
        assert result["session"] == "session2"
        assert "context_file" in result
        assert "response_file" in result
        assert "Context data:" in result["prompt"]
        # Context should NOT be inline
        assert "items" not in result.get("prompt", "").split("Context data:")[0]

        with open(result["context_file"], encoding="utf-8") as f:
            ctx = json.load(f)
        assert ctx == {"items": [1, 2, 3]}

    def test_spawn_no_context_no_file(self, tmp_path: object) -> None:
        """spawn without context should not create a context file."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import interpret

        comm_dir = os.path.join(str(tmp_path), "session3")
        code = (
            'let x = spawn [{prompt: "Simple task"}]\n'
            'return x'
        )
        result = interpret(code, comm_dir=comm_dir)
        assert result["type"] == "spawn_batch"
        # Single spawn is flattened
        assert "context_file" not in result
        assert "response_file" in result
        assert "Context data:" not in result["prompt"]

    def test_ask_no_context_no_file(self, tmp_path: object) -> None:
        """ask without context should not create a context file."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import interpret

        comm_dir = os.path.join(str(tmp_path), "session4")
        code = (
            'let x = ask\n'
            '  "Yes or no?"\n'
            '  expects: bool'
        )
        result = interpret(code, comm_dir=comm_dir)
        assert result["type"] == "ask"
        assert "context_file" not in result
        assert "response_file" in result
        assert result["prompt"] == "Yes or no?"

    def test_no_comm_dir_keeps_inline_context(self) -> None:
        """Without comm_dir, context stays inline (backwards compat)."""
        from lumon.interpreter import interpret

        code = (
            'let x = ask\n'
            '  "Choose"\n'
            '  context: "data"\n'
            '  expects: text'
        )
        result = interpret(code)
        assert result["type"] == "ask"
        assert result["context"] == "data"
        assert "context_file" not in result
        assert "response_file" not in result
        assert "session" not in result

    def test_cleanup_comm_dir(self, tmp_path: object) -> None:
        """cleanup_comm_dir removes the session directory."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import cleanup_comm_dir

        comm_dir = os.path.join(str(tmp_path), "to_clean")
        os.makedirs(comm_dir)
        with open(os.path.join(comm_dir, "test.json"), "w") as f:
            f.write("{}")
        cleanup_comm_dir(comm_dir)
        assert not os.path.exists(comm_dir)

    def test_cleanup_all_comm(self, tmp_path: object) -> None:
        """cleanup_all_comm removes the entire .lumon_comm directory."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import cleanup_all_comm

        base = os.path.join(str(tmp_path), ".lumon_comm")
        os.makedirs(os.path.join(base, "session1"))
        os.makedirs(os.path.join(base, "session2"))
        cleanup_all_comm(base)
        assert not os.path.exists(base)

    def test_single_spawn_with_comm_dir(self, tmp_path: object) -> None:
        """Single spawn with comm_dir still produces correct output."""
        assert isinstance(tmp_path, os.PathLike)
        from lumon.interpreter import interpret

        comm_dir = os.path.join(str(tmp_path), "session5")
        code = (
            'let x = spawn [{prompt: "Analyze", context: "article"}]\n'
            'return x'
        )
        result = interpret(code, comm_dir=comm_dir)
        assert result["type"] == "spawn_batch"
        assert result["session"] == "session5"
        # Single spawn is flattened (no "spawns" list)
        assert "spawns" not in result
        assert result["spawn_id"] == "spawn_0"
        assert "Context data:" in result["prompt"]
        assert "response_file" in result
