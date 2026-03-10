"""Unit tests for lumon.daemon — daemon helpers testable without os.fork()."""

from __future__ import annotations

import json
import os
import threading
import time
from unittest.mock import patch

from lumon.daemon import (
    _STALE_AGE,
    SuspendEvent,
    _cleanup_response_files,
    _kill_daemon,
    _kill_process_tree,
    _poll_ask_response,
    _poll_spawn_responses,
    _reap_child,
    _run_daemon,
    _session_age,
    _unwrap_spawn_response,
    _validate_spawn_responses,
    _write_output,
    _write_pid,
    cleanup_stale_sessions,
    is_daemon_alive,
    read_daemon_output,
)


class TestUnwrapSpawnResponse:
    def test_unwraps_wrapper(self) -> None:
        assert _unwrap_spawn_response({"result": 42, "spawn_id": 0}) == 42

    def test_passes_through_plain_value(self) -> None:
        assert _unwrap_spawn_response("hello") == "hello"

    def test_passes_through_dict_without_spawn_id(self) -> None:
        val = {"result": 42, "other": "key"}
        assert _unwrap_spawn_response(val) is val

    def test_passes_through_dict_without_result(self) -> None:
        val = {"spawn_id": 0, "other": "key"}
        assert _unwrap_spawn_response(val) is val

    def test_unwraps_none_result(self) -> None:
        assert _unwrap_spawn_response({"result": None, "spawn_id": 0}) is None


class TestValidateSpawnResponses:
    def test_valid_text_response(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [{"expects": "text"}]}
        assert _validate_spawn_responses(["hello"], envelope) is None

    def test_invalid_text_response_is_map(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [{"expects": "text"}]}
        err = _validate_spawn_responses([{"value": "hello"}], envelope)
        assert err is not None
        assert "spawn_0" in err
        assert "expected text" in err

    def test_valid_number_response(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [{"expects": "number"}]}
        assert _validate_spawn_responses([42], envelope) is None

    def test_valid_list_response(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [{"expects": "list"}]}
        assert _validate_spawn_responses([[1, 2]], envelope) is None

    def test_no_expects_skips_validation(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [{}]}
        assert _validate_spawn_responses([{"anything": True}], envelope) is None

    def test_single_spawn_envelope(self) -> None:
        # Single-spawn envelopes spread fields directly (no "spawns" key)
        envelope = {"type": "spawn_batch", "expects": "text"}
        assert _validate_spawn_responses(["hello"], envelope) is None

    def test_single_spawn_envelope_invalid(self) -> None:
        envelope = {"type": "spawn_batch", "expects": "text"}
        err = _validate_spawn_responses([42], envelope)
        assert err is not None
        assert "expected text" in err

    def test_multi_spawn_validates_each(self) -> None:
        envelope = {"type": "spawn_batch", "spawns": [
            {"expects": "text"},
            {"expects": "number"},
        ]}
        # First is wrong
        err = _validate_spawn_responses([42, 10], envelope)
        assert err is not None
        assert "spawn_0" in err


class TestSuspendEvent:
    def test_suspend_for_ask(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        envelope = {"type": "ask", "prompt": "q?"}
        result_box: list[object] = []

        def worker() -> None:
            result_box.append(se.suspend_for_ask(envelope))

        t = threading.Thread(target=worker)
        t.start()

        # Wait for envelope to be set
        deadline = time.monotonic() + 2
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope == envelope

        se.resume_with_ask("the answer")
        t.join(timeout=2)
        assert result_box == ["the answer"]

    def test_suspend_for_spawns(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        envelope = {"type": "spawn_batch", "spawns": [{}, {}]}
        result_box: list[object] = []

        def worker() -> None:
            result_box.append(se.suspend_for_spawns(envelope))

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.monotonic() + 2
        while se.envelope is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert se.envelope == envelope

        se.resume_with_spawns(["resp A", "resp B"])
        t.join(timeout=2)
        assert result_box == [["resp A", "resp B"]]

    def test_clear_envelope(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        se = SuspendEvent(str(tmp_path))
        se._envelope = {"type": "ask"}
        se.clear_envelope()
        assert se.envelope is None


class TestPollAskResponse:
    def test_returns_response_when_file_appears(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        resp_path = os.path.join(comm_dir, "ask_response.json")

        # Write response after a small delay
        def write_later() -> None:
            time.sleep(0.1)
            with open(resp_path, "w", encoding="utf-8") as f:
                json.dump("the answer", f)

        t = threading.Thread(target=write_later)
        t.start()
        result = _poll_ask_response(comm_dir, timeout=2)
        t.join()
        assert result == "the answer"

    def test_returns_none_on_timeout(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        result = _poll_ask_response(str(tmp_path), timeout=0.1)
        assert result is None


class TestPollSpawnResponses:
    def test_returns_all_responses(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        for i, resp in enumerate(["A", "B"]):
            with open(os.path.join(comm_dir, f"spawn_{i}_response.json"), "w") as f:
                json.dump(resp, f)
        result = _poll_spawn_responses(comm_dir, 2, timeout=1)
        assert result == ["A", "B"]

    def test_waits_for_all_files(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        # Write first file immediately
        with open(os.path.join(comm_dir, "spawn_0_response.json"), "w") as f:
            json.dump("A", f)

        # Write second after delay
        def write_later() -> None:
            time.sleep(0.1)
            with open(os.path.join(comm_dir, "spawn_1_response.json"), "w") as f:
                json.dump("B", f)

        t = threading.Thread(target=write_later)
        t.start()
        result = _poll_spawn_responses(comm_dir, 2, timeout=2)
        t.join()
        assert result == ["A", "B"]

    def test_returns_none_on_timeout(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        result = _poll_spawn_responses(str(tmp_path), 2, timeout=0.1)
        assert result is None

    def test_unwraps_spawn_wrapper(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "spawn_0_response.json"), "w") as f:
            json.dump({"result": "inner", "spawn_id": 0}, f)
        result = _poll_spawn_responses(comm_dir, 1, timeout=1)
        assert result == ["inner"]


class TestWriteOutput:
    def test_writes_json(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        _write_output(comm_dir, {"type": "result", "value": 42})
        with open(os.path.join(comm_dir, "output.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"type": "result", "value": 42}

    def test_overwrites_existing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        _write_output(comm_dir, {"type": "result", "value": 1})
        _write_output(comm_dir, {"type": "result", "value": 2})
        with open(os.path.join(comm_dir, "output.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert data["value"] == 2


class TestWritePid:
    def test_writes_pid(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        _write_pid(comm_dir)
        with open(os.path.join(comm_dir, "pid"), encoding="utf-8") as f:
            pid = int(f.read().strip())
        assert pid == os.getpid()


class TestCleanupResponseFiles:
    def test_removes_response_and_context_files(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        for name in ["ask_response.json", "spawn_0_response.json", "ask_context.json", "pid", "output.json"]:
            with open(os.path.join(comm_dir, name), "w") as f:
                f.write("{}")
        _cleanup_response_files(comm_dir)
        remaining = set(os.listdir(comm_dir))
        assert "pid" in remaining
        assert "output.json" in remaining
        assert "ask_response.json" not in remaining
        assert "spawn_0_response.json" not in remaining
        assert "ask_context.json" not in remaining


class TestIsDaemonAlive:
    def test_alive_with_current_pid(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write(str(os.getpid()))
        assert is_daemon_alive(comm_dir) is True

    def test_dead_with_nonexistent_pid(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("999999999")
        assert is_daemon_alive(comm_dir) is False

    def test_no_pid_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        assert is_daemon_alive(str(tmp_path)) is False

    def test_invalid_pid_content(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("not_a_number")
        assert is_daemon_alive(comm_dir) is False


class TestReadDaemonOutput:
    def test_reads_output(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        _write_output(comm_dir, {"type": "result", "value": 99})
        result = read_daemon_output(comm_dir, timeout=1)
        assert result == {"type": "result", "value": 99}
        # File should be removed after reading
        assert not os.path.isfile(os.path.join(comm_dir, "output.json"))

    def test_returns_none_on_timeout(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        result = read_daemon_output(str(tmp_path), timeout=0.1)
        assert result is None

    def test_waits_for_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)

        def write_later() -> None:
            time.sleep(0.1)
            _write_output(comm_dir, {"type": "result", "value": "late"})

        t = threading.Thread(target=write_later)
        t.start()
        result = read_daemon_output(comm_dir, timeout=2)
        t.join()
        assert result == {"type": "result", "value": "late"}


class TestCleanupStaleSessions:
    def test_removes_dead_pid_sessions(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        base = str(tmp_path)
        dead_dir = os.path.join(base, "dead_sess")
        os.makedirs(dead_dir)
        with open(os.path.join(dead_dir, "pid"), "w") as f:
            f.write("999999999")
        cleanup_stale_sessions(base)
        assert not os.path.isdir(dead_dir)

    def test_leaves_alive_sessions(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        base = str(tmp_path)
        alive_dir = os.path.join(base, "alive_sess")
        os.makedirs(alive_dir)
        with open(os.path.join(alive_dir, "pid"), "w") as f:
            f.write(str(os.getpid()))
        cleanup_stale_sessions(base)
        assert os.path.isdir(alive_dir)

    def test_noop_when_base_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        cleanup_stale_sessions(os.path.join(str(tmp_path), "nonexistent"))

    def test_ignores_sessions_without_pid(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        base = str(tmp_path)
        no_pid_dir = os.path.join(base, "no_pid_sess")
        os.makedirs(no_pid_dir)
        with open(os.path.join(no_pid_dir, "data.json"), "w") as f:
            f.write("{}")
        cleanup_stale_sessions(base)
        # Should remain — no pid file means it's not recognized as a daemon session
        assert os.path.isdir(no_pid_dir)

    def test_removes_stale_alive_sessions(self, tmp_path: object) -> None:
        """Sessions older than 24h are killed and removed even if daemon is alive."""
        assert isinstance(tmp_path, os.PathLike)
        base = str(tmp_path)
        stale_dir = os.path.join(base, "stale_sess")
        os.makedirs(stale_dir)
        pid_file = os.path.join(stale_dir, "pid")
        # Use a non-existent PID but backdate the file to trigger age check.
        # We need the daemon to appear "alive" for the age branch, so use
        # current PID but mock _STALE_AGE to 0 to make everything stale.
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        # Backdate pid file to 25 hours ago
        old_time = time.time() - _STALE_AGE - 3600
        os.utime(pid_file, (old_time, old_time))
        # The cleanup should detect the age and remove (it will try to kill
        # our own process, but we mock _kill_daemon to avoid that)
        with patch("lumon.daemon._kill_daemon"):
            cleanup_stale_sessions(base)
        assert not os.path.isdir(stale_dir)

    def test_leaves_fresh_alive_sessions(self, tmp_path: object) -> None:
        """Recent sessions with alive daemons are not cleaned up."""
        assert isinstance(tmp_path, os.PathLike)
        base = str(tmp_path)
        fresh_dir = os.path.join(base, "fresh_sess")
        os.makedirs(fresh_dir)
        with open(os.path.join(fresh_dir, "pid"), "w") as f:
            f.write(str(os.getpid()))
        cleanup_stale_sessions(base)
        assert os.path.isdir(fresh_dir)


class TestSessionAge:
    def test_age_of_recent_session(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("1234")
        age = _session_age(comm_dir)
        assert 0 <= age < 5  # just created, should be near 0

    def test_age_of_old_session(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        pid_file = os.path.join(comm_dir, "pid")
        with open(pid_file, "w") as f:
            f.write("1234")
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(pid_file, (old_time, old_time))
        age = _session_age(comm_dir)
        assert 7100 < age < 7300

    def test_age_without_pid_file(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        assert _session_age(str(tmp_path)) == 0.0


class TestKillProcessTree:
    def test_sends_sigterm_then_sigkill_via_killpg(self) -> None:
        """Sends SIGTERM then SIGKILL via process group."""
        import signal as sig_mod
        calls: list[tuple[str, int, int]] = []

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))

        with patch("lumon.daemon.os.killpg", side_effect=fake_killpg), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)

        assert calls == [
            ("killpg", 12345, sig_mod.SIGTERM),
            ("killpg", 12345, sig_mod.SIGKILL),
        ]

    def test_falls_back_to_single_kill_when_killpg_fails(self) -> None:
        """Falls back to os.kill when os.killpg raises OSError."""
        import signal as sig_mod
        calls: list[tuple[str, int, int]] = []

        def fake_killpg(pid: int, sig: int) -> None:
            raise OSError("No such process group")

        def fake_kill(pid: int, sig: int) -> None:
            calls.append(("kill", pid, sig))

        with patch("lumon.daemon.os.killpg", side_effect=fake_killpg), \
             patch("lumon.daemon.os.kill", side_effect=fake_kill), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)

        assert calls == [
            ("kill", 12345, sig_mod.SIGTERM),
            ("kill", 12345, sig_mod.SIGKILL),
        ]

    def test_noop_when_process_already_dead(self) -> None:
        """No error when process is already dead."""
        with patch("lumon.daemon.os.killpg", side_effect=ProcessLookupError), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)  # should not raise

    def test_process_dies_during_grace_period(self) -> None:
        """SIGTERM succeeds but SIGKILL gets ProcessLookupError (died during grace)."""
        import signal as sig_mod
        calls: list[tuple[str, int, int]] = []

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))
            if sig == sig_mod.SIGKILL:
                raise ProcessLookupError("No such process")

        with patch("lumon.daemon.os.killpg", side_effect=fake_killpg), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)  # should not raise

        assert calls == [
            ("killpg", 12345, sig_mod.SIGTERM),
            ("killpg", 12345, sig_mod.SIGKILL),
        ]

    def test_sigterm_killpg_ok_sigkill_falls_back_to_kill(self) -> None:
        """SIGTERM via killpg works, SIGKILL killpg fails, falls back to os.kill."""
        import signal as sig_mod
        calls: list[tuple[str, int, int]] = []

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))
            if sig == sig_mod.SIGKILL:
                raise OSError("process group gone")

        def fake_kill(pid: int, sig: int) -> None:
            calls.append(("kill", pid, sig))

        with patch("lumon.daemon.os.killpg", side_effect=fake_killpg), \
             patch("lumon.daemon.os.kill", side_effect=fake_kill), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)

        assert calls == [
            ("killpg", 12345, sig_mod.SIGTERM),
            ("killpg", 12345, sig_mod.SIGKILL),
            ("kill", 12345, sig_mod.SIGKILL),
        ]

    def test_sigterm_permission_error_still_tries_sigkill(self) -> None:
        """PermissionError on SIGTERM doesn't prevent SIGKILL attempt.

        PermissionError is a subclass of OSError, so killpg(SIGTERM) PermissionError
        falls into the single-PID fallback (os.kill SIGTERM), which also gets
        PermissionError and falls through to SIGKILL.
        """
        import signal as sig_mod
        calls: list[tuple[str, int, int]] = []

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))
            if sig == sig_mod.SIGTERM:
                raise PermissionError("not allowed")

        def fake_kill(pid: int, sig: int) -> None:
            calls.append(("kill", pid, sig))
            if sig == sig_mod.SIGTERM:
                raise PermissionError("not allowed")

        with patch("lumon.daemon.os.killpg", side_effect=fake_killpg), \
             patch("lumon.daemon.os.kill", side_effect=fake_kill), \
             patch("lumon.daemon.time.sleep"):
            _kill_process_tree(12345)

        # killpg(SIGTERM) → PermissionError → falls to os.kill(SIGTERM) →
        # PermissionError → falls through to SIGKILL → killpg(SIGKILL) succeeds
        assert calls == [
            ("killpg", 12345, sig_mod.SIGTERM),
            ("kill", 12345, sig_mod.SIGTERM),
            ("killpg", 12345, sig_mod.SIGKILL),
        ]


class TestReapChild:
    def test_reaps_immediately(self) -> None:
        """Reaps child on first try."""
        with patch("lumon.daemon.os.waitpid", return_value=(123, 0)):
            _reap_child(123)  # should not raise

    def test_retries_then_reaps(self) -> None:
        """Retries WNOHANG until child exits."""
        results = iter([(0, 0), (0, 0), (123, 0)])
        with patch("lumon.daemon.os.waitpid", side_effect=results), \
             patch("lumon.daemon.time.sleep"):
            _reap_child(123)

    def test_gives_up_after_retries(self) -> None:
        """Returns without error when all WNOHANG retries return (0, 0)."""
        with patch("lumon.daemon.os.waitpid", return_value=(0, 0)), \
             patch("lumon.daemon.time.sleep"):
            _reap_child(123)  # should not raise, just give up

    def test_noop_when_already_reaped(self) -> None:
        """No error when child is already reaped."""
        with patch("lumon.daemon.os.waitpid", side_effect=ChildProcessError):
            _reap_child(123)  # should not raise


class TestKillDaemon:
    def test_no_pid_file(self, tmp_path: object) -> None:
        """No-op when pid file doesn't exist."""
        assert isinstance(tmp_path, os.PathLike)
        _kill_daemon(str(tmp_path))  # should not raise

    def test_invalid_pid_content(self, tmp_path: object) -> None:
        """No-op when pid file contains non-numeric content."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("not_a_number")
        _kill_daemon(comm_dir)  # should not raise

    def test_nonexistent_pid(self, tmp_path: object) -> None:
        """No-op when PID doesn't exist."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("999999999")
        _kill_daemon(comm_dir)  # should not raise

    def test_calls_kill_process_tree(self, tmp_path: object) -> None:
        """Delegates to _kill_process_tree with the PID from the file."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("12345")
        with patch("lumon.daemon._kill_process_tree") as mock_kill:
            _kill_daemon(comm_dir)
            mock_kill.assert_called_once_with(12345)


class TestRunDaemonSpawnHandling:
    """Tests that _run_daemon correctly handles single- and multi-spawn envelopes."""

    def test_single_spawn_waits_for_response(self, tmp_path: object) -> None:
        """Single-spawn envelope (no 'spawns' key) polls for spawn_0_response.json."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)

        def run_fn(suspend: SuspendEvent) -> dict:
            # Simulate single spawn: envelope has no "spawns" key
            envelope = {"type": "spawn_batch", "spawn_id": "spawn_0", "prompt": "do it"}
            responses = suspend.suspend_for_spawns(envelope)
            return {"type": "result", "value": responses[0]}

        # Write the spawn response file after a brief delay
        def write_response() -> None:
            time.sleep(0.2)
            resp_path = os.path.join(comm_dir, "spawn_0_response.json")
            with open(resp_path, "w", encoding="utf-8") as f:
                json.dump("the spawn result", f)

        writer = threading.Thread(target=write_response)
        writer.start()

        _run_daemon(run_fn, comm_dir, "test_session")
        writer.join()

        # _run_daemon writes final result to output.json
        output_path = os.path.join(comm_dir, "output.json")
        assert os.path.isfile(output_path)
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["type"] == "result"
        assert data["value"] == "the spawn result"

    def test_multi_spawn_waits_for_all_responses(self, tmp_path: object) -> None:
        """Multi-spawn envelope ('spawns' list) polls for all response files."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = str(tmp_path)

        def run_fn(suspend: SuspendEvent) -> dict:
            envelope = {"type": "spawn_batch", "spawns": [
                {"spawn_id": "spawn_0", "prompt": "A"},
                {"spawn_id": "spawn_1", "prompt": "B"},
            ]}
            responses = suspend.suspend_for_spawns(envelope)
            return {"type": "result", "value": responses}

        def write_responses() -> None:
            time.sleep(0.2)
            for i, val in enumerate(["resp_A", "resp_B"]):
                path = os.path.join(comm_dir, f"spawn_{i}_response.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(val, f)

        writer = threading.Thread(target=write_responses)
        writer.start()

        _run_daemon(run_fn, comm_dir, "test_session")
        writer.join()

        output_path = os.path.join(comm_dir, "output.json")
        assert os.path.isfile(output_path)
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["type"] == "result"
        assert data["value"] == ["resp_A", "resp_B"]
