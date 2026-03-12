"""Lumon scheduler — manages scheduled execution of Lumon scripts via launchd."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

LUMON_HOME = Path.home() / ".lumon"
SCHEDULES_FILE = "schedules.json"
LOGS_DIR = "logs"


@dataclass
class Schedule:
    id: str
    file: str
    schedule_type: str  # "once", "every", "cron"
    schedule_value: str
    working_dir: str
    created_at: str
    start_at: str = ""  # ISO 8601 datetime (naive) — delays first run until this time


# ---------------------------------------------------------------------------
# Interval / cron parsing
# ---------------------------------------------------------------------------

_INTERVAL_SUFFIXES: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_interval(value: str) -> int:
    """Parse an interval string like '30s', '5m', '1h', '2d' into seconds."""
    if not value:
        raise ValueError("empty interval string")
    suffix = value[-1].lower()
    if suffix not in _INTERVAL_SUFFIXES:
        raise ValueError(f"invalid interval suffix '{suffix}' — use s, m, h, or d")
    try:
        amount = int(value[:-1])
    except ValueError:
        raise ValueError(f"invalid interval number: {value[:-1]}") from None
    if amount <= 0:
        raise ValueError("interval must be positive")
    return amount * _INTERVAL_SUFFIXES[suffix]


_CRON_FIELDS = ("Minute", "Hour", "Day", "Month", "Weekday")


def parse_cron(expr: str) -> dict[str, int]:
    """Parse a 5-field cron expression into a launchd StartCalendarInterval dict.

    Only supports literal values and '*' (wildcard). Step values (*/5) are not
    supported since launchd's StartCalendarInterval doesn't support them.
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"cron expression must have 5 fields, got {len(parts)}")

    result: dict[str, int] = {}
    for i, part in enumerate(parts):
        if part == "*":
            continue  # wildcard — omit from dict
        if "/" in part:
            raise ValueError(f"step values ('{part}') are not supported — launchd cannot represent them")
        if "-" in part:
            raise ValueError(f"range values ('{part}') are not supported — launchd cannot represent them")
        if "," in part:
            raise ValueError(f"list values ('{part}') are not supported — launchd cannot represent them")
        try:
            val = int(part)
        except ValueError:
            raise ValueError(f"invalid cron field value: {part}") from None
        result[_CRON_FIELDS[i]] = val
    return result


def parse_at(value: str) -> dict[str, int]:
    """Parse an ISO 8601 datetime into a launchd StartCalendarInterval dict."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"invalid datetime: {value} — use ISO 8601 format (e.g. 2026-03-08T09:00)"
        ) from None
    return {
        "Month": dt.month,
        "Day": dt.day,
        "Hour": dt.hour,
        "Minute": dt.minute,
    }


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------


def _project_hash(working_dir: str) -> str:
    """Short hash to scope data per project directory."""
    return hashlib.sha256(str(Path(working_dir).resolve()).encode()).hexdigest()[:8]


def _project_dir(working_dir: str) -> Path:
    """Return ~/.lumon/<project_hash>/ for the given project."""
    return LUMON_HOME / _project_hash(working_dir)


def _schedules_path(working_dir: str) -> Path:
    return _project_dir(working_dir) / SCHEDULES_FILE


def _logs_path(working_dir: str) -> Path:
    return _project_dir(working_dir) / LOGS_DIR


def load_schedules(working_dir: str) -> list[Schedule]:
    """Load all schedules from ~/.lumon/<project>/schedules.json."""
    path = _schedules_path(working_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Schedule(**entry) for entry in data]


def save_schedules(working_dir: str, schedules: list[Schedule]) -> None:
    """Save schedules to ~/.lumon/<project>/schedules.json."""
    path = _schedules_path(working_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(s) for s in schedules], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _next_id(schedules: list[Schedule]) -> str:
    """Generate the next sched_XX id."""
    max_num = 0
    for s in schedules:
        if s.id.startswith("sched_"):
            try:
                num = int(s.id[6:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"sched_{max_num + 1:02d}"


def _find_schedule(schedules: list[Schedule], job_id: str) -> Schedule:
    """Find a schedule by ID or raise ValueError."""
    for s in schedules:
        if s.id == job_id:
            return s
    raise ValueError(f"schedule not found: {job_id}")


_DEPLOY_REQUIRED_FILES = (
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/hooks/sandbox-guard.py",
)


def _require_deployed_agent(working_dir: str) -> None:
    """Ensure the working directory has a fully deployed Lumon agent.

    Checks for CLAUDE.md, settings.json, and the sandbox-guard hook.
    All three are required for safe scheduled execution.
    """
    abs_dir = str(Path(working_dir).resolve())
    missing = [f for f in _DEPLOY_REQUIRED_FILES if not (Path(abs_dir) / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"incomplete Lumon agent deployment in {abs_dir} "
            f"(missing: {', '.join(missing)}) "
            f"— run 'lumon deploy {abs_dir}' first"
        )


def _validate_start_at(start_at: str) -> None:
    """Validate an ISO 8601 start_at string."""
    if start_at:
        try:
            datetime.fromisoformat(start_at)
        except ValueError:
            raise ValueError(
                f"invalid start time: {start_at} — use ISO 8601 format "
                f"(e.g. 2026-03-08T09:00)"
            ) from None


def _validate_schedule_value(schedule_type: str, schedule_value: str) -> None:
    """Validate a schedule type and value pair."""
    if schedule_type == "every":
        parse_interval(schedule_value)
    elif schedule_type == "cron":
        parse_cron(schedule_value)
    elif schedule_type == "once":
        parse_at(schedule_value)
    else:
        raise ValueError(f"unknown schedule type: {schedule_type}")


def add_schedule(
    working_dir: str,
    file: str,
    schedule_type: str,
    schedule_value: str,
    start_at: str = "",
) -> Schedule:
    """Create a new scheduled job and install the launchd plist."""
    if platform.system() != "Darwin":
        raise RuntimeError(
            "lumon schedule is only supported on macOS (launchd) "
            "— Linux support is not yet available"
        )

    abs_file = str(Path(file).resolve())
    if not Path(abs_file).exists():
        raise FileNotFoundError(f"script not found: {file}")

    _require_deployed_agent(working_dir)
    _validate_schedule_value(schedule_type, schedule_value)
    _validate_start_at(start_at)

    schedules = load_schedules(working_dir)
    job_id = _next_id(schedules)
    abs_working_dir = str(Path(working_dir).resolve())

    sched = Schedule(
        id=job_id,
        file=abs_file,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        working_dir=abs_working_dir,
        created_at=datetime.now().isoformat(timespec="seconds"),
        start_at=start_at,
    )
    schedules.append(sched)
    save_schedules(working_dir, schedules)
    _install_launchd(sched)
    return sched


def remove_schedule(working_dir: str, job_id: str) -> None:
    """Remove a scheduled job and unload its launchd plist."""
    schedules = load_schedules(working_dir)
    found = _find_schedule(schedules, job_id)
    _uninstall_launchd(found)
    schedules = [s for s in schedules if s.id != job_id]
    save_schedules(working_dir, schedules)


def edit_schedule(
    working_dir: str,
    job_id: str,
    schedule_type: str,
    schedule_value: str,
    start_at: str = "",
) -> Schedule:
    """Update an existing job's schedule and reinstall its plist."""
    _validate_schedule_value(schedule_type, schedule_value)
    _validate_start_at(start_at)

    schedules = load_schedules(working_dir)
    found = _find_schedule(schedules, job_id)

    _uninstall_launchd(found)
    found.schedule_type = schedule_type
    found.schedule_value = schedule_value
    found.start_at = start_at
    save_schedules(working_dir, schedules)
    _install_launchd(found)
    return found


def list_schedules(working_dir: str) -> list[Schedule]:
    """Return all scheduled jobs."""
    return load_schedules(working_dir)


def get_logs(working_dir: str, job_id: str, limit: int = 10) -> list[dict]:
    """Read the most recent log entries for a job."""
    log_dir = _logs_path(working_dir) / job_id
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("*.json"), reverse=True)[:limit]
    logs: list[dict] = []
    for f in files:
        try:
            logs.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return logs


# ---------------------------------------------------------------------------
# Job execution (called by launchd via `lumon schedule _run <id>`)
# ---------------------------------------------------------------------------


def run_job(working_dir: str, job_id: str) -> int:
    """Execute a scheduled job via claude and log the result."""
    schedules = load_schedules(working_dir)
    try:
        found = _find_schedule(schedules, job_id)
    except ValueError:
        print(f"error: schedule not found: {job_id}", file=sys.stderr)
        return 1

    # Verify the agent is deployed (CLAUDE.md + settings + sandbox-guard hook)
    try:
        _require_deployed_agent(found.working_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Skip if before the configured start time
    if found.start_at:
        # Strip timezone — datetime.now() is naive, so comparison must be too
        start_dt = datetime.fromisoformat(found.start_at).replace(tzinfo=None)
        if datetime.now() < start_dt:
            result = {"type": "skipped", "reason": f"before start time ({found.start_at})"}
            _log_result(working_dir, job_id, found, result)
            return 0

    result = _run_with_claude(found)
    _log_result(working_dir, job_id, found, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("type") != "error" else 1


def _log_result(working_dir: str, job_id: str, schedule: Schedule, result: dict) -> None:
    """Write a log entry for a job execution."""
    now = datetime.now()
    log_dir = _logs_path(working_dir) / job_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "timestamp": now.isoformat(timespec="seconds"),
        "job_id": job_id,
        "file": schedule.file,
        "result": result,
    }
    log_file = log_dir / f"{now.strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(
        json.dumps(log_entry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _resolve_claude() -> str:
    """Return the absolute path to the claude CLI, or 'claude' as fallback."""
    return shutil.which("claude") or "claude"


def _run_with_claude(schedule: Schedule) -> dict:
    """Run a Lumon script via the claude CLI subprocess.

    Uses ``--output-format json`` to get structured metadata (turns,
    duration, cost) alongside the result.  Falls back to plain text
    if JSON parsing fails.
    """
    stderr_path = _logs_path(schedule.working_dir) / schedule.id / "stderr.log"
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(stderr_path, "a", encoding="utf-8") as stderr_file:
            result = subprocess.run(
                [
                    _resolve_claude(), "--print", "--verbose",
                    "--output-format", "json",
                    f"Run this Lumon script and handle all ask/spawn prompts: {schedule.file}",
                ],
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                text=True,
                cwd=schedule.working_dir,
                check=False,
            )
        if result.returncode != 0:
            return {"type": "error", "message": f"claude exited with code {result.returncode}"}

        # Try to parse structured JSON output from --output-format json
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                summary = _build_summary(data)
                value = data.get("result", result.stdout.strip())
                out: dict = {"type": "result", "value": value}
                if summary:
                    out["summary"] = summary
                return out
            # Claude may return a list of messages — extract last assistant text
            if isinstance(data, list):
                value = _extract_result_from_messages(data)
                return {"type": "result", "value": value}
            return {"type": "result", "value": result.stdout.strip()}
        except (json.JSONDecodeError, KeyError):
            return {"type": "result", "value": result.stdout.strip()}
    except FileNotFoundError:
        return {"type": "error", "message": "claude CLI not found — install it to run scheduled scripts"}


def _extract_result_from_messages(messages: list) -> str:
    """Extract the final assistant text from a list of conversation messages."""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            # content may be a list of blocks
            if isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                if texts:
                    return "\n".join(texts)
    # Fallback: join all string items
    return "\n".join(str(m) for m in messages)


def _build_summary(data: dict) -> str:
    """Build a human-readable summary from Claude's JSON output metadata."""
    parts: list[str] = []
    num_turns = data.get("num_turns")
    if num_turns is not None:
        parts.append(f"{num_turns} turn{'s' if num_turns != 1 else ''}")
    duration_ms = data.get("duration_ms")
    if duration_ms is not None:
        secs = duration_ms / 1000
        if secs >= 60:
            parts.append(f"{secs / 60:.1f}min")
        else:
            parts.append(f"{secs:.0f}s")
    cost = data.get("cost_usd")
    if cost is not None:
        parts.append(f"${cost:.3f}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Launchd plist management
# ---------------------------------------------------------------------------


def _plist_label(schedule: Schedule) -> str:
    """Generate a unique launchd label for a schedule."""
    return f"com.lumon.{_project_hash(schedule.working_dir)}.{schedule.id}"


def _plist_path(schedule: Schedule) -> Path:
    """Return the path to the launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{_plist_label(schedule)}.plist"


def _build_plist(schedule: Schedule) -> dict:
    """Build a launchd plist dictionary for a schedule."""
    # Prefer the lumon entry point from the same venv as the running Python
    lumon_path_candidate = Path(sys.executable).parent / "lumon"
    if lumon_path_candidate.exists():
        lumon_path = str(lumon_path_candidate)
    else:
        lumon_path = shutil.which("lumon") or "lumon"

    plist: dict = {
        "Label": _plist_label(schedule),
        "ProgramArguments": [
            lumon_path,
            "--working-dir",
            schedule.working_dir,
            "schedule",
            "_run",
            schedule.id,
        ],
        "StandardOutPath": str(_logs_path(schedule.working_dir) / schedule.id / "stdout.log"),
        "StandardErrorPath": str(_logs_path(schedule.working_dir) / schedule.id / "stderr.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        },
    }

    if schedule.schedule_type == "every":
        plist["StartInterval"] = parse_interval(schedule.schedule_value)
    elif schedule.schedule_type == "cron":
        plist["StartCalendarInterval"] = parse_cron(schedule.schedule_value)
    elif schedule.schedule_type == "once":
        plist["StartCalendarInterval"] = parse_at(schedule.schedule_value)

    return plist


def _install_launchd(schedule: Schedule) -> None:
    """Write and load a launchd plist for the given schedule."""
    plist_path = _plist_path(schedule)
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    plist_data = _build_plist(schedule)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)

    subprocess.run(
        ["launchctl", "load", str(plist_path)],
        check=True,
        capture_output=True,
    )


def _uninstall_launchd(schedule: Schedule) -> None:
    """Unload and remove a launchd plist for the given schedule."""
    plist_path = _plist_path(schedule)
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            check=False,
            capture_output=True,
        )
        plist_path.unlink()
