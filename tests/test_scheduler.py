"""Tests for lumon.scheduler — interval/cron parsing, CRUD, plist generation, run_job."""

from __future__ import annotations

import argparse
import json
import plistlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# pylint: disable=import-outside-toplevel

import pytest

from lumon.scheduler import (
    Schedule,
    _build_plist,
    _next_id,
    _plist_label,
    add_schedule,
    edit_schedule,
    get_logs,
    list_schedules,
    load_schedules,
    parse_at,
    parse_cron,
    parse_interval,
    remove_schedule,
    run_job,
    save_schedules,
)


# ---------------------------------------------------------------------------
# parse_interval
# ---------------------------------------------------------------------------


class TestParseInterval:
    def test_seconds(self) -> None:
        assert parse_interval("30s") == 30

    def test_minutes(self) -> None:
        assert parse_interval("5m") == 300

    def test_hours(self) -> None:
        assert parse_interval("1h") == 3600

    def test_days(self) -> None:
        assert parse_interval("2d") == 172800

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="empty interval"):
            parse_interval("")

    def test_invalid_suffix(self) -> None:
        with pytest.raises(ValueError, match="invalid interval suffix"):
            parse_interval("5x")

    def test_invalid_number(self) -> None:
        with pytest.raises(ValueError, match="invalid interval number"):
            parse_interval("abcm")

    def test_zero(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            parse_interval("0h")

    def test_negative(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            parse_interval("-1h")

    def test_case_insensitive(self) -> None:
        assert parse_interval("5M") == 300


# ---------------------------------------------------------------------------
# parse_cron
# ---------------------------------------------------------------------------


class TestParseCron:
    def test_every_day_at_9(self) -> None:
        assert parse_cron("0 9 * * *") == {"Minute": 0, "Hour": 9}

    def test_all_wildcards(self) -> None:
        assert parse_cron("* * * * *") == {}

    def test_all_specified(self) -> None:
        assert parse_cron("30 14 1 6 3") == {
            "Minute": 30,
            "Hour": 14,
            "Day": 1,
            "Month": 6,
            "Weekday": 3,
        }

    def test_wrong_field_count(self) -> None:
        with pytest.raises(ValueError, match="must have 5 fields"):
            parse_cron("0 9 *")

    def test_step_rejected(self) -> None:
        with pytest.raises(ValueError, match="step values"):
            parse_cron("*/5 * * * *")

    def test_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="range values"):
            parse_cron("1-5 * * * *")

    def test_list_rejected(self) -> None:
        with pytest.raises(ValueError, match="list values"):
            parse_cron("1,2,3 * * * *")

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError, match="invalid cron field"):
            parse_cron("abc * * * *")


# ---------------------------------------------------------------------------
# parse_at
# ---------------------------------------------------------------------------


class TestParseAt:
    def test_datetime(self) -> None:
        result = parse_at("2026-03-08T09:00")
        assert result == {"Month": 3, "Day": 8, "Hour": 9, "Minute": 0}

    def test_with_seconds(self) -> None:
        result = parse_at("2026-12-25T14:30:00")
        assert result == {"Month": 12, "Day": 25, "Hour": 14, "Minute": 30}

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="invalid datetime"):
            parse_at("not-a-date")


# ---------------------------------------------------------------------------
# _next_id
# ---------------------------------------------------------------------------


class TestNextId:
    def test_empty(self) -> None:
        assert _next_id([]) == "sched_01"

    def test_sequential(self) -> None:
        schedules = [
            Schedule(id="sched_01", file="a.lumon", schedule_type="every",
                     schedule_value="1h", working_dir=".", created_at="2026-01-01"),
            Schedule(id="sched_02", file="b.lumon", schedule_type="every",
                     schedule_value="2h", working_dir=".", created_at="2026-01-01"),
        ]
        assert _next_id(schedules) == "sched_03"

    def test_gap(self) -> None:
        schedules = [
            Schedule(id="sched_01", file="a.lumon", schedule_type="every",
                     schedule_value="1h", working_dir=".", created_at="2026-01-01"),
            Schedule(id="sched_05", file="b.lumon", schedule_type="every",
                     schedule_value="2h", working_dir=".", created_at="2026-01-01"),
        ]
        assert _next_id(schedules) == "sched_06"


# ---------------------------------------------------------------------------
# Schedule CRUD (with tmp_path)
# ---------------------------------------------------------------------------


class TestScheduleCRUD:
    def test_save_and_load(self, tmp_path: Path) -> None:
        sched = Schedule(
            id="sched_01", file="test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])
        loaded = load_schedules(str(tmp_path))
        assert len(loaded) == 1
        assert loaded[0].id == "sched_01"
        assert loaded[0].file == "test.lumon"

    def test_load_empty(self, tmp_path: Path) -> None:
        assert load_schedules(str(tmp_path)) == []

    @patch("lumon.scheduler.platform.system", return_value="Darwin")
    @patch("lumon.scheduler._install_launchd")
    def test_add_schedule(self, mock_install: MagicMock, _mock_sys: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        sched = add_schedule(str(tmp_path), str(script), "every", "1h")
        assert sched.id == "sched_01"
        assert sched.schedule_type == "every"
        assert sched.schedule_value == "1h"
        mock_install.assert_called_once()

        # Verify it was persisted
        loaded = load_schedules(str(tmp_path))
        assert len(loaded) == 1

    @patch("lumon.scheduler.platform.system", return_value="Linux")
    def test_add_schedule_linux_rejected(self, _mock_sys: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        with pytest.raises(RuntimeError, match="only supported on macOS"):
            add_schedule(str(tmp_path), str(script), "every", "1h")

    @patch("lumon.scheduler.platform.system", return_value="Darwin")
    @patch("lumon.scheduler._install_launchd")
    def test_add_schedule_file_not_found(self, _mock_install: MagicMock, _mock_sys: MagicMock, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="script not found"):
            add_schedule(str(tmp_path), str(tmp_path / "nonexistent.lumon"), "every", "1h")

    @patch("lumon.scheduler._uninstall_launchd")
    def test_remove_schedule(self, mock_uninstall: MagicMock, tmp_path: Path) -> None:
        sched = Schedule(
            id="sched_01", file="test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])
        remove_schedule(str(tmp_path), "sched_01")
        mock_uninstall.assert_called_once()
        assert load_schedules(str(tmp_path)) == []

    def test_remove_not_found(self, tmp_path: Path) -> None:
        save_schedules(str(tmp_path), [])
        with pytest.raises(ValueError, match="schedule not found"):
            remove_schedule(str(tmp_path), "sched_99")

    @patch("lumon.scheduler._uninstall_launchd")
    @patch("lumon.scheduler._install_launchd")
    def test_edit_schedule(self, mock_install: MagicMock, mock_uninstall: MagicMock, tmp_path: Path) -> None:
        sched = Schedule(
            id="sched_01", file="test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])
        updated = edit_schedule(str(tmp_path), "sched_01", "cron", "0 9 * * *")
        assert updated.schedule_type == "cron"
        assert updated.schedule_value == "0 9 * * *"
        mock_uninstall.assert_called_once()
        mock_install.assert_called_once()

    def test_edit_not_found(self, tmp_path: Path) -> None:
        save_schedules(str(tmp_path), [])
        with pytest.raises(ValueError, match="schedule not found"):
            edit_schedule(str(tmp_path), "sched_99", "every", "1h")

    @patch("lumon.scheduler.platform.system", return_value="Darwin")
    @patch("lumon.scheduler._install_launchd")
    def test_add_unknown_type(self, _mock_install: MagicMock, _mock_sys: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        with pytest.raises(ValueError, match="unknown schedule type"):
            add_schedule(str(tmp_path), str(script), "invalid", "1h")

    def test_edit_unknown_type(self, tmp_path: Path) -> None:
        sched = Schedule(
            id="sched_01", file="test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])
        with pytest.raises(ValueError, match="unknown schedule type"):
            edit_schedule(str(tmp_path), "sched_01", "invalid", "1h")

    def test_list_schedules(self, tmp_path: Path) -> None:
        s1 = Schedule(id="sched_01", file="a.lumon", schedule_type="every",
                      schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01")
        s2 = Schedule(id="sched_02", file="b.lumon", schedule_type="cron",
                      schedule_value="0 9 * * *", working_dir=str(tmp_path), created_at="2026-01-02")
        save_schedules(str(tmp_path), [s1, s2])
        result = list_schedules(str(tmp_path))
        assert len(result) == 2
        assert result[0].id == "sched_01"
        assert result[1].id == "sched_02"


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


class TestLogs:
    def test_get_logs_empty(self, tmp_path: Path) -> None:
        assert get_logs(str(tmp_path), "sched_01") == []

    def test_get_logs(self, tmp_path: Path) -> None:
        log_dir = tmp_path / ".lumon" / "logs" / "sched_01"
        log_dir.mkdir(parents=True)
        entry = {"timestamp": "2026-01-01T00:00:00", "job_id": "sched_01", "result": {"type": "result", "value": 42}}
        (log_dir / "20260101_000000.json").write_text(json.dumps(entry))
        logs = get_logs(str(tmp_path), "sched_01")
        assert len(logs) == 1
        assert logs[0]["result"]["value"] == 42

    def test_get_logs_malformed(self, tmp_path: Path) -> None:
        """Malformed JSON log files are silently skipped."""
        log_dir = tmp_path / ".lumon" / "logs" / "sched_01"
        log_dir.mkdir(parents=True)
        (log_dir / "20260101_000000.json").write_text("not valid json")
        (log_dir / "20260102_000000.json").write_text('{"valid": true}')
        logs = get_logs(str(tmp_path), "sched_01")
        assert len(logs) == 1
        assert logs[0]["valid"] is True

    def test_get_logs_limit(self, tmp_path: Path) -> None:
        log_dir = tmp_path / ".lumon" / "logs" / "sched_01"
        log_dir.mkdir(parents=True)
        for i in range(5):
            entry = {"timestamp": f"2026-01-0{i+1}T00:00:00", "job_id": "sched_01", "result": {"type": "result"}}
            (log_dir / f"2026010{i+1}_000000.json").write_text(json.dumps(entry))
        logs = get_logs(str(tmp_path), "sched_01", limit=3)
        assert len(logs) == 3


# ---------------------------------------------------------------------------
# Plist generation
# ---------------------------------------------------------------------------


class TestPlist:
    def _make_schedule(self, schedule_type: str = "every", schedule_value: str = "1h") -> Schedule:
        return Schedule(
            id="sched_01", file="/tmp/test.lumon", schedule_type=schedule_type,
            schedule_value=schedule_value, working_dir="/tmp/project",
            created_at="2026-01-01",
        )

    def test_plist_label(self) -> None:
        sched = self._make_schedule()
        label = _plist_label(sched)
        assert label.startswith("com.lumon.")
        assert label.endswith(".sched_01")

    def test_plist_every(self) -> None:
        sched = self._make_schedule("every", "1h")
        plist = _build_plist(sched)
        assert plist["StartInterval"] == 3600
        assert "StartCalendarInterval" not in plist
        assert "schedule" in plist["ProgramArguments"]
        assert "_run" in plist["ProgramArguments"]
        assert "sched_01" in plist["ProgramArguments"]

    def test_plist_cron(self) -> None:
        sched = self._make_schedule("cron", "0 9 * * *")
        plist = _build_plist(sched)
        assert plist["StartCalendarInterval"] == {"Minute": 0, "Hour": 9}
        assert "StartInterval" not in plist

    def test_plist_once(self) -> None:
        sched = self._make_schedule("once", "2026-03-08T09:00")
        plist = _build_plist(sched)
        assert plist["StartCalendarInterval"] == {"Month": 3, "Day": 8, "Hour": 9, "Minute": 0}

    def test_plist_is_valid_xml(self) -> None:
        sched = self._make_schedule("every", "30m")
        plist = _build_plist(sched)
        # Verify it can be serialized to valid plist XML
        data = plistlib.dumps(plist)
        roundtrip = plistlib.loads(data)
        assert roundtrip["Label"] == plist["Label"]
        assert roundtrip["StartInterval"] == 1800

    def test_plist_working_dir_in_args(self) -> None:
        sched = self._make_schedule()
        plist = _build_plist(sched)
        args = plist["ProgramArguments"]
        assert "--working-dir" in args
        idx = args.index("--working-dir")
        assert args[idx + 1] == "/tmp/project"


# ---------------------------------------------------------------------------
# run_job
# ---------------------------------------------------------------------------


class TestStartAt:
    @patch("lumon.scheduler.platform.system", return_value="Darwin")
    @patch("lumon.scheduler._install_launchd")
    def test_add_with_start_at(self, _mock_install: MagicMock, _mock_sys: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        sched = add_schedule(str(tmp_path), str(script), "every", "1h", start_at="2026-06-01T09:00")
        assert sched.start_at == "2026-06-01T09:00"
        loaded = load_schedules(str(tmp_path))
        assert loaded[0].start_at == "2026-06-01T09:00"

    @patch("lumon.scheduler.platform.system", return_value="Darwin")
    @patch("lumon.scheduler._install_launchd")
    def test_add_invalid_start_at(self, _mock_install: MagicMock, _mock_sys: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        with pytest.raises(ValueError, match="invalid start time"):
            add_schedule(str(tmp_path), str(script), "every", "1h", start_at="not-a-date")

    @patch("lumon.scheduler._run_with_claude")
    def test_run_job_skips_before_start(self, mock_claude: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        sched = Schedule(
            id="sched_01", file=str(script), schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
            start_at="2099-01-01T00:00",  # far in the future
        )
        save_schedules(str(tmp_path), [sched])
        exit_code = run_job(str(tmp_path), "sched_01")
        assert exit_code == 0
        mock_claude.assert_not_called()
        # Verify a "skipped" log was written
        logs = get_logs(str(tmp_path), "sched_01")
        assert len(logs) == 1
        assert logs[0]["result"]["type"] == "skipped"

    @patch("lumon.scheduler._run_with_claude")
    def test_run_job_runs_after_start(self, mock_claude: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        sched = Schedule(
            id="sched_01", file=str(script), schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
            start_at="2020-01-01T00:00",  # in the past
        )
        save_schedules(str(tmp_path), [sched])
        mock_claude.return_value = {"type": "result", "value": "done"}
        exit_code = run_job(str(tmp_path), "sched_01")
        assert exit_code == 0
        mock_claude.assert_called_once()


class TestRunJob:
    @patch("lumon.scheduler._run_with_claude")
    def test_run_job_success(self, mock_claude: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("return 42")
        sched = Schedule(
            id="sched_01", file=str(script), schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])

        mock_claude.return_value = {"type": "result", "value": "42"}
        exit_code = run_job(str(tmp_path), "sched_01")
        assert exit_code == 0
        mock_claude.assert_called_once()

        # Verify log was written
        log_dir = tmp_path / ".lumon" / "logs" / "sched_01"
        log_files = [f for f in log_dir.glob("*.json") if f.stem not in ("stdout", "stderr")]
        assert len(log_files) == 1

    def test_run_job_not_found(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        save_schedules(str(tmp_path), [])
        exit_code = run_job(str(tmp_path), "sched_99")
        assert exit_code == 1
        assert "schedule not found" in capsys.readouterr().err

    @patch("lumon.scheduler._run_with_claude")
    def test_run_job_error_result(self, mock_claude: MagicMock, tmp_path: Path) -> None:
        script = tmp_path / "job.lumon"
        script.write_text("fail")
        sched = Schedule(
            id="sched_01", file=str(script), schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        save_schedules(str(tmp_path), [sched])

        mock_claude.return_value = {"type": "error", "message": "something broke"}
        exit_code = run_job(str(tmp_path), "sched_01")
        assert exit_code == 1

    @patch("lumon.scheduler.subprocess.run")
    def test_run_with_claude_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from lumon.scheduler import _run_with_claude
        sched = Schedule(
            id="sched_01", file="/tmp/test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        result = _run_with_claude(sched)
        assert result == {"type": "result", "value": "done"}

    @patch("lumon.scheduler.subprocess.run")
    def test_run_with_claude_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from lumon.scheduler import _run_with_claude
        sched = Schedule(
            id="sched_01", file="/tmp/test.lumon", schedule_type="every",
            schedule_value="1h", working_dir=str(tmp_path), created_at="2026-01-01",
        )
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="something went wrong")
        result = _run_with_claude(sched)
        assert result == {"type": "error", "message": "something went wrong"}

    @patch("lumon.scheduler.subprocess.run", side_effect=FileNotFoundError)
    def test_run_with_claude_not_found(self, _mock_run: MagicMock) -> None:
        from lumon.scheduler import _run_with_claude
        sched = Schedule(
            id="sched_01", file="/tmp/test.lumon", schedule_type="every",
            schedule_value="1h", working_dir="/tmp", created_at="2026-01-01",
        )
        result = _run_with_claude(sched)
        assert result["type"] == "error"
        assert "claude CLI not found" in result["message"]

    @patch("lumon.scheduler.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300))
    def test_run_with_claude_timeout(self, _mock_run: MagicMock) -> None:
        from lumon.scheduler import _run_with_claude
        sched = Schedule(
            id="sched_01", file="/tmp/test.lumon", schedule_type="every",
            schedule_value="1h", working_dir="/tmp", created_at="2026-01-01",
        )
        result = _run_with_claude(sched)
        assert result["type"] == "error"
        assert "timed out" in result["message"]


# ---------------------------------------------------------------------------
# CLI integration (argparse)
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    def test_schedule_in_subcommands(self) -> None:
        from lumon.cli import _SUBCOMMANDS
        assert "schedule" in _SUBCOMMANDS

    def test_schedule_add_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "add", "job.lumon", "--every", "1h"])
        assert args.command == "schedule"
        assert args.schedule_command == "add"
        assert args.file == "job.lumon"
        assert args.every == "1h"

    def test_schedule_list_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "list"])
        assert args.command == "schedule"
        assert args.schedule_command == "list"

    def test_schedule_edit_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "edit", "sched_01", "--cron", "0 9 * * *"])
        assert args.command == "schedule"
        assert args.schedule_command == "edit"
        assert args.id == "sched_01"
        assert args.cron == "0 9 * * *"

    def test_schedule_remove_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "remove", "sched_01"])
        assert args.command == "schedule"
        assert args.schedule_command == "remove"
        assert args.id == "sched_01"

    def test_schedule_logs_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "logs", "sched_01", "--limit", "5"])
        assert args.command == "schedule"
        assert args.schedule_command == "logs"
        assert args.id == "sched_01"
        assert args.limit == 5

    def test_schedule_run_parser(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "_run", "sched_01"])
        assert args.command == "schedule"
        assert args.schedule_command == "_run"
        assert args.id == "sched_01"

    def test_schedule_add_mutually_exclusive(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["schedule", "add", "job.lumon", "--every", "1h", "--cron", "0 9 * * *"])

    def test_schedule_add_with_start(self) -> None:
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "add", "job.lumon", "--every", "1h", "--start", "2026-03-09T09:00"])
        assert args.every == "1h"
        assert args.start == "2026-03-09T09:00"

    def test_schedule_add_no_option_parses(self) -> None:
        """Without --at/--every/--cron, argparse accepts it (interactive prompt kicks in)."""
        from lumon.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["schedule", "add", "job.lumon"])
        assert args.file == "job.lumon"
        assert args.at is None
        assert args.every is None
        assert args.cron is None


class TestScheduleInteractive:
    def test_no_subcommand_shows_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        from lumon.cli import cmd_schedule
        args = argparse.Namespace(command="schedule")
        # schedule_command not set → shows help
        result = cmd_schedule(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "Examples:" in out
        assert "--every" in out
        assert "--cron" in out

    @patch("builtins.input", side_effect=["2", "1h", "2026-03-09T09:00"])
    def test_prompt_every_with_start(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, svalue, start_at = _prompt_schedule_type()
        assert stype == "every"
        assert svalue == "1h"
        assert start_at == "2026-03-09T09:00"

    @patch("builtins.input", side_effect=["2", "1h", ""])
    def test_prompt_every_no_start(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, svalue, start_at = _prompt_schedule_type()
        assert stype == "every"
        assert svalue == "1h"
        assert start_at == ""

    @patch("builtins.input", side_effect=["1", "2026-03-08T09:00"])
    def test_prompt_once(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, svalue, start_at = _prompt_schedule_type()
        assert stype == "once"
        assert svalue == "2026-03-08T09:00"
        assert start_at == ""

    @patch("builtins.input", side_effect=["3", "0 9 * * *"])
    def test_prompt_cron(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, svalue, start_at = _prompt_schedule_type()
        assert stype == "cron"
        assert svalue == "0 9 * * *"
        assert start_at == ""

    @patch("builtins.input", side_effect=["7"])
    def test_prompt_invalid(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, _svalue, _start = _prompt_schedule_type()
        assert stype is None

    @patch("builtins.input", side_effect=EOFError)
    def test_prompt_eof(self, _mock_input: MagicMock) -> None:
        from lumon.cli import _prompt_schedule_type
        stype, _svalue, _start = _prompt_schedule_type()
        assert stype is None
