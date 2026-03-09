"""Persistent process daemon for ask/spawn suspension.

When execution hits an ask or spawn_batch, the process forks:
- Parent prints the suspension envelope and exits (returns control to agent)
- Child stays alive as a daemon, polling for response files, and resumes
  execution from the exact suspension point.
"""

from __future__ import annotations

import json
import os
import signal
import shutil
import threading
import time
from collections.abc import Callable

from lumon.errors import LumonError
from lumon.serializer import deserialize

_POLL_INTERVAL = 0.2  # seconds
_MAX_WAIT = 3600  # 1 hour default timeout
_STALE_AGE = 86400  # 24 hours — sessions older than this are cleaned up


def _unwrap_spawn_response(value: object) -> object:
    """Unwrap ``{result: ..., spawn_id: ...}`` wrapper if present."""
    if isinstance(value, dict) and "result" in value and "spawn_id" in value:
        return value["result"]
    return value


class SuspendEvent:
    """Thread-safe suspension mechanism for ask/spawn.

    The worker thread calls `suspend()` to block until a response is available.
    The daemon loop calls `resume()` after finding response files.
    """

    def __init__(self, comm_dir: str) -> None:
        self.comm_dir = comm_dir
        self._event = threading.Event()
        self._envelope: dict | None = None
        self._response: object = None
        self._batch_responses: list[object] | None = None

    def suspend_for_ask(self, envelope: dict) -> object:
        """Called from worker thread. Blocks until response is available."""
        self._envelope = envelope
        self._event.clear()
        self._event.wait()
        return self._response

    def suspend_for_spawns(self, envelope: dict) -> list[object]:
        """Called from worker thread. Blocks until all spawn responses are available."""
        self._envelope = envelope
        self._event.clear()
        self._event.wait()
        assert self._batch_responses is not None
        return self._batch_responses

    @property
    def envelope(self) -> dict | None:
        return self._envelope

    def resume_with_ask(self, response: object) -> None:
        """Called from daemon loop after reading ask_response.json."""
        self._response = response
        self._event.set()

    def resume_with_spawns(self, responses: list[object]) -> None:
        """Called from daemon loop after reading all spawn response files."""
        self._batch_responses = responses
        self._event.set()

    def clear_envelope(self) -> None:
        """Clear the current envelope so we can detect the next suspension."""
        self._envelope = None


def _write_output(comm_dir: str, data: dict) -> None:
    """Write output JSON for `lumon respond` to read."""
    path = os.path.join(comm_dir, "output.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp_path, path)


def _write_pid(comm_dir: str) -> None:
    """Write the daemon PID to the comm directory."""
    with open(os.path.join(comm_dir, "pid"), "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _poll_ask_response(comm_dir: str, timeout: float = _MAX_WAIT) -> object | None:
    """Poll for ask_response.json. Returns parsed response or None on timeout."""
    path = os.path.join(comm_dir, "ask_response.json")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return deserialize(json.load(f))
        time.sleep(_POLL_INTERVAL)
    return None


def _poll_spawn_responses(
    comm_dir: str, batch_size: int, timeout: float = _MAX_WAIT,
) -> list[object] | None:
    """Poll for spawn response files. Returns list of responses or None on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        responses: list[object] = []
        all_found = True
        for i in range(batch_size):
            path = os.path.join(comm_dir, f"spawn_{i}_response.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                responses.append(_unwrap_spawn_response(deserialize(raw)))
            else:
                all_found = False
                break
        if all_found:
            return responses
        time.sleep(_POLL_INTERVAL)
    return None


def _cleanup_response_files(comm_dir: str) -> None:
    """Remove response files after they've been consumed."""
    for name in os.listdir(comm_dir):
        if name.endswith("_response.json") or name.endswith("_context.json"):
            try:
                os.remove(os.path.join(comm_dir, name))
            except OSError:
                pass


def _run_daemon(
    run_fn: Callable[[SuspendEvent], dict],
    comm_dir: str,
    session: str,
) -> None:
    """Daemon process: runs interpreter, polls for responses, writes output.

    This function runs in the forked child process. It:
    1. Writes PID file
    2. Starts worker thread running the interpreter
    3. When worker suspends (ask/spawn), writes output.json with the envelope
    4. Polls for response files
    5. Resumes worker with responses
    6. Repeats until completion or error
    """
    _write_pid(comm_dir)
    suspend = SuspendEvent(comm_dir)
    worker_result: list[dict] = []
    worker_error: list[Exception] = []
    worker_done = threading.Event()

    def _worker() -> None:
        try:
            result = run_fn(suspend)
            worker_result.append(result)
        except Exception as e:
            worker_error.append(e)
        finally:
            worker_done.set()

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    first_output_written = False

    while True:
        # Wait for either suspension or completion
        while True:
            if worker_done.is_set():
                break
            if suspend.envelope is not None:
                break
            time.sleep(0.01)

        if worker_done.is_set():
            # Execution completed
            if worker_result:
                _write_output(comm_dir, worker_result[0])
            elif worker_error:
                err = worker_error[0]
                if isinstance(err, LumonError):
                    _write_output(comm_dir, err.to_envelope())
                else:
                    _write_output(comm_dir, {"type": "error", "message": str(err)})
            return

        # Suspension occurred
        envelope = suspend.envelope
        assert envelope is not None

        if not first_output_written:
            # First suspension: write envelope as first_output.json for parent to read
            first_path = os.path.join(comm_dir, "first_output.json")
            tmp_path = first_path + ".tmp"
            tagged = dict(envelope)
            tagged["session"] = session
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(tagged, f, ensure_ascii=False)
            os.replace(tmp_path, first_path)
            first_output_written = True
        else:
            # Subsequent suspension: write as output.json for `lumon respond`
            tagged = dict(envelope)
            tagged["session"] = session
            _write_output(comm_dir, tagged)

        # Poll for responses
        if envelope.get("type") == "ask":
            response = _poll_ask_response(comm_dir)
            if response is None:
                _write_output(comm_dir, {
                    "type": "error",
                    "message": "Daemon timed out waiting for ask response",
                })
                return
            _cleanup_response_files(comm_dir)
            # Clear envelope before resuming so we can detect next suspension
            suspend.clear_envelope()
            suspend.resume_with_ask(response)
        elif envelope.get("type") == "spawn_batch":
            spawns = envelope.get("spawns", [])
            batch_size = len(spawns) if isinstance(spawns, list) else 0
            responses = _poll_spawn_responses(comm_dir, batch_size)
            if responses is None:
                _write_output(comm_dir, {
                    "type": "error",
                    "message": "Daemon timed out waiting for spawn responses",
                })
                return
            _cleanup_response_files(comm_dir)
            suspend.clear_envelope()
            suspend.resume_with_spawns(responses)
        else:
            return


def run_with_daemon(
    run_fn: Callable[[SuspendEvent], dict],
    comm_dir: str,
    session: str,
) -> dict:
    """Fork before running interpreter: child becomes daemon, parent reads first output.

    Args:
        run_fn: Function that runs the interpreter. Receives a SuspendEvent
                 and returns the final result dict. When execution suspends,
                 it blocks on the SuspendEvent.
        comm_dir: Path to .lumon_comm/<session>/
        session: Session ID string

    Returns:
        The envelope to print to stdout (ask/spawn for suspension, result for completion).
    """
    os.makedirs(comm_dir, exist_ok=True)

    # Fork before any threads are created
    pid = os.fork()

    if pid == 0:
        # Child: become daemon
        try:
            os.setsid()
        except OSError:
            pass

        # Redirect stdio to /dev/null
        try:
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            os.close(devnull)
        except OSError:
            pass

        try:
            _run_daemon(run_fn, comm_dir, session)
        except Exception as exc:
            # Write error to output.json so parent/respond can detect it
            try:
                _write_output(comm_dir, {"type": "error", "message": str(exc)})
            except Exception:
                pass
        os._exit(0)

    # Parent: wait for first_output.json or completion
    first_path = os.path.join(comm_dir, "first_output.json")
    output_path = os.path.join(comm_dir, "output.json")
    deadline = time.monotonic() + 30  # 30s timeout for initial execution

    while time.monotonic() < deadline:
        # Check for first suspension envelope
        if os.path.isfile(first_path):
            with open(first_path, encoding="utf-8") as f:
                data = json.load(f)
            try:
                os.remove(first_path)
            except OSError:
                pass
            return data
        # Check for completion (no suspension at all)
        if os.path.isfile(output_path):
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
            try:
                os.remove(output_path)
            except OSError:
                pass
            # Child completed without suspension — wait for it
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            return data
        time.sleep(0.05)

    # Timeout waiting for child
    return {"type": "error", "message": "Timed out waiting for interpreter to start"}


def is_daemon_alive(comm_dir: str) -> bool:
    """Check if the daemon process for a session is alive."""
    pid_file = os.path.join(comm_dir, "pid")
    if not os.path.isfile(pid_file):
        return False
    try:
        with open(pid_file, encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def read_daemon_output(comm_dir: str, timeout: float = 30) -> dict | None:
    """Poll for output.json written by the daemon. Returns parsed dict or None."""
    path = os.path.join(comm_dir, "output.json")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Remove the output file after reading
            try:
                os.remove(path)
            except OSError:
                pass
            return data
        time.sleep(_POLL_INTERVAL)
    return None


def _session_age(session_dir: str) -> float:
    """Return the age of a session in seconds, based on the PID file mtime."""
    pid_file = os.path.join(session_dir, "pid")
    if os.path.isfile(pid_file):
        return time.time() - os.path.getmtime(pid_file)
    return 0.0


def _kill_daemon(session_dir: str) -> None:
    """Send SIGKILL to the daemon process if it's still alive."""
    pid_file = os.path.join(session_dir, "pid")
    if not os.path.isfile(pid_file):
        return
    try:
        with open(pid_file, encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGKILL)
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        pass


def cleanup_stale_sessions(base_dir: str = ".lumon_comm") -> None:
    """Remove dead or stale (24h+) daemon sessions.

    Two cleanup criteria:
    1. Daemon process is dead — remove the session directory
    2. Session is older than 24 hours — kill the daemon and remove
    """
    if not os.path.isdir(base_dir):
        return
    for name in os.listdir(base_dir):
        session_dir = os.path.join(base_dir, name)
        if not os.path.isdir(session_dir):
            continue
        pid_file = os.path.join(session_dir, "pid")
        if not os.path.isfile(pid_file):
            continue
        if not is_daemon_alive(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
        elif _session_age(session_dir) > _STALE_AGE:
            _kill_daemon(session_dir)
            shutil.rmtree(session_dir, ignore_errors=True)
