"""Tests for interpret_with_suspend — daemon-mode interpreter entry point."""

from __future__ import annotations

import os
import threading
import time

from lumon.daemon import SuspendEvent
from lumon.interpreter import interpret_with_suspend


class TestInterpretWithSuspend:
    def test_simple_return(self) -> None:
        result = interpret_with_suspend("return 42")
        assert result["type"] == "result"
        assert result["value"] == 42

    def test_error(self) -> None:
        result = interpret_with_suspend("return undefined_var")
        assert result["type"] == "error"
        assert "Undefined" in result["message"]

    def test_ask_without_suspend_raises_ask_signal(self) -> None:
        """Without suspend_event, ask raises AskSignal and returns ask envelope."""
        result = interpret_with_suspend('let x = ask\n  "question?"')
        assert result["type"] == "ask"
        assert "question?" in result["prompt"]

    def test_ask_with_suspend_event(self, tmp_path: object) -> None:
        """With SuspendEvent, ask blocks and resumes with the provided response."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        def worker() -> None:
            r = interpret_with_suspend(
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
        result = interpret_with_suspend('let a = spawn\n  "task"\nreturn a')
        assert result["type"] == "spawn_batch"

    def test_spawn_with_suspend_event(self, tmp_path: object) -> None:
        """With SuspendEvent, spawn batch blocks and resumes with responses."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        def worker() -> None:
            r = interpret_with_suspend(
                'let a = spawn\n  "task A"\nlet b = spawn\n  "task B"\nreturn [a, b]',
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

        se.clear_envelope()
        se.resume_with_spawns(["resp A", "resp B"])
        t.join(timeout=5)

        assert len(result_box) == 1
        assert result_box[0]["type"] == "result"
        assert result_box[0]["value"] == ["resp A", "resp B"]

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
        result = interpret_with_suspend(code)
        assert result["type"] == "error"
        assert "depth" in result["message"].lower() or "limit" in result["message"].lower()

    def test_logs_included(self) -> None:
        result = interpret_with_suspend('log("hello")\nreturn 1')
        assert result["type"] == "result"
        assert result.get("logs") == ["hello"]

    def test_return_signal(self) -> None:
        """ReturnSignal from top level is handled."""
        result = interpret_with_suspend("return 99")
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
            r = interpret_with_suspend(code, suspend_event=se)
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
        """Ask followed by spawn: ask suspends first, then spawns batch at end."""
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        result_box: list[dict] = []

        code = (
            'let a = ask\n'
            '  "confirm?"\n'
            'let s = spawn\n'
            '  "analyze"\n'
            'return a'
        )

        def worker() -> None:
            r = interpret_with_suspend(code, suspend_event=se)
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

        # Spawns are batched at end — suspend_for_spawns fires
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
        # When pending spawns exist, result value is the spawn responses
        assert result_box[0]["value"] == ["spawn_result"]
