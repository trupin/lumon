"""Tests for interpret — daemon-mode interpreter entry point."""

from __future__ import annotations

import os
import threading
import time

from lumon.daemon import SuspendEvent
from lumon.interpreter import interpret


class TestInterpretWithSuspend:
    def test_simple_return(self) -> None:
        result = interpret("return 42")
        assert result["type"] == "result"
        assert result["value"] == 42

    def test_error(self) -> None:
        result = interpret("return undefined_var")
        assert result["type"] == "error"
        assert "Undefined" in result["message"]

    def test_ask_without_suspend_raises_ask_signal(self) -> None:
        """Without suspend_event, ask raises AskSignal and returns ask envelope."""
        result = interpret('let x = ask\n  "question?"')
        assert result["type"] == "ask"
        assert "question?" in result["prompt"]

    def test_ask_with_suspend_event(self, tmp_path: object) -> None:
        """With SuspendEvent, ask blocks and resumes with the provided response."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        def worker() -> None:
            r = interpret(
                'let x = ask\n  "q?"\nreturn x',
                suspend_event=se,
            )
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        # Wait for suspension
        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "ask"

        se.clear_envelope()
        se.resume_with_ask("the answer")
        t.join(timeout=5)

        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == "the answer"

    def test_spawn_without_suspend_returns_batch(self) -> None:
        """Without suspend_event, spawn returns spawn_batch envelope."""
        result = interpret('let a = spawn [{prompt: "task"}]\nreturn a')
        assert result["type"] == "spawn_batch"

    def test_spawn_with_suspend_event(self, tmp_path: object) -> None:
        """With SuspendEvent, spawn blocks in-place and resumes with responses."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        code = (
            'let results = spawn [\n'
            '  {prompt: "task A"},\n'
            '  {prompt: "task B"}\n'
            ']\n'
            'return results'
        )

        def worker() -> None:
            r = interpret(code, suspend_event=se)
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "spawn_batch"

        se.clear_envelope()
        se.resume_with_spawns(["resp A", "resp B"])
        t.join(timeout=5)

        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == ["resp A", "resp B"]

    def test_single_spawn_with_suspend_event(self, tmp_path: object) -> None:
        """Single spawn: envelope has no 'spawns' key (fields spread directly)."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        def worker() -> None:
            r = interpret(
                'let a = spawn [{prompt: "single task"}]\nreturn a',
                suspend_event=se,
            )
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "spawn_batch"
        # Single spawn: fields spread directly, no "spawns" key
        assert "spawns" not in se.envelope

        se.clear_envelope()
        se.resume_with_spawns(["the result"])
        t.join(timeout=5)

        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == ["the result"]

    def test_recursion_error(self) -> None:
        code = (
            'define ns.rec\n'
            '  "recurse"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "r"\n'
            '\n'
            'implement ns.rec\n'
            '  return ns.rec(n + 1)\n'
            '\n'
            'return ns.rec(0)'
        )
        result = interpret(code)
        assert result["type"] == "error"
        assert "depth" in result["message"].lower() or "limit" in result["message"].lower()

    def test_logs_included(self) -> None:
        result = interpret('log("hello")\nreturn 1')
        assert result["type"] == "result"
        assert result.get("logs") == ["hello"]

    def test_return_signal(self) -> None:
        """ReturnSignal from top level is handled."""
        result = interpret("return 99")
        assert result["type"] == "result"
        assert result["value"] == 99

    def test_chained_ask(self, tmp_path: object) -> None:
        """Chained ask: ask → respond → ask → respond → result."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        code = (
            'let a = ask\n'
            '  "first?"\n'
            'let b = ask\n'
            '  "second?"\n'
            'return [a, b]'
        )

        def worker() -> None:
            r = interpret(code, suspend_event=se)
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        # First ask
        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "ask"
        assert "first?" in se.envelope["prompt"]

        se.clear_envelope()
        se.resume_with_ask("answer1")

        # Second ask
        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "ask"
        assert "second?" in se.envelope["prompt"]

        se.clear_envelope()
        se.resume_with_ask("answer2")

        t.join(timeout=5)
        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == ["answer1", "answer2"]

    def test_ask_then_spawn(self, tmp_path: object) -> None:
        """Ask followed by spawn: ask blocks first, then spawn blocks in-place."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        code = (
            'let a = ask\n'
            '  "confirm?"\n'
            'let s = spawn [{prompt: "analyze"}]\n'
            'return [a, s]'
        )

        def worker() -> None:
            r = interpret(code, suspend_event=se)
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        # Ask suspends first
        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "ask"

        se.clear_envelope()
        se.resume_with_ask("confirmed")

        # Spawn blocks in-place — suspend_for_spawns fires
        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "spawn_batch"

        se.clear_envelope()
        se.resume_with_spawns(["spawn_result"])

        t.join(timeout=5)
        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == ["confirmed", ["spawn_result"]]

    def test_spawn_post_processing(self, tmp_path: object) -> None:
        """Spawn result can be used in subsequent computation."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        code = (
            'let results = spawn [{prompt: "analyze"}]\n'
            'let count = list.length(results)\n'
            'return count'
        )

        def worker() -> None:
            r = interpret(code, suspend_event=se)
            result_box.append(r)

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.monotonic() + 5
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope is not None
        assert se.envelope["type"] == "spawn_batch"

        se.clear_envelope()
        se.resume_with_spawns(["the result"])

        t.join(timeout=5)
        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == 1
