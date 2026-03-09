"""CLI handlers for the `lumon schedule` subcommand."""

from __future__ import annotations

import argparse
import json
import sys

from lumon.scheduler import (
    add_schedule,
    edit_schedule,
    get_logs,
    list_schedules,
    remove_schedule,
    run_job,
)


def cmd_schedule(args: argparse.Namespace) -> int:
    """Manage scheduled execution of Lumon scripts."""
    sub = getattr(args, "schedule_command", None)
    if sub is None:
        _print_schedule_help()
        return 0

    working_dir = "."

    if sub == "add":
        schedule_type, schedule_value, start_at = _schedule_opts_from_args(args)
        if schedule_type is None:
            schedule_type, schedule_value, start_at = _prompt_schedule_type()
            if schedule_type is None:
                return 1
        try:
            sched = add_schedule(working_dir, args.file, schedule_type, schedule_value, start_at=start_at)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        msg = f"Created {sched.id}: {sched.file} ({sched.schedule_type} {sched.schedule_value})"
        if sched.start_at:
            msg += f" starting {sched.start_at}"
        print(msg)
        print(
            "\nNote: macOS may show a \"Background Items Added\" notification.\n"
            "This is normal — lumon registers a launchd agent to run your script\n"
            "on schedule. You can manage it in System Settings > General > Login Items."
        )
        return 0

    if sub == "list":
        schedules = list_schedules(working_dir)
        if not schedules:
            print("No scheduled jobs.")
            return 0
        print(f"{'ID':<12} {'Type':<6} {'Schedule':<20} {'Start':<22} {'File'}")
        print("-" * 90)
        for s in schedules:
            start = s.start_at if s.start_at else "-"
            print(f"{s.id:<12} {s.schedule_type:<6} {s.schedule_value:<20} {start:<22} {s.file}")
        return 0

    if sub == "edit":
        schedule_type, schedule_value, start_at = _schedule_opts_from_args(args)
        if schedule_type is None:
            schedule_type, schedule_value, start_at = _prompt_schedule_type()
            if schedule_type is None:
                return 1
        try:
            sched = edit_schedule(working_dir, args.id, schedule_type, schedule_value, start_at=start_at)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        msg = f"Updated {sched.id}: {sched.schedule_type} {sched.schedule_value}"
        if sched.start_at:
            msg += f" starting {sched.start_at}"
        print(msg)
        return 0

    if sub == "remove":
        try:
            remove_schedule(working_dir, args.id)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"Removed {args.id}")
        return 0

    if sub == "logs":
        limit = getattr(args, "limit", 10) or 10
        logs = get_logs(working_dir, args.id, limit=limit)
        if not logs:
            print(f"No logs for {args.id}.")
            return 0
        for entry in logs:
            ts = entry.get("timestamp", "?")
            result = entry.get("result", {})
            rtype = result.get("type", "?")
            print(f"[{ts}] {rtype}: {json.dumps(result, ensure_ascii=False)}")
        return 0

    if sub == "_run":
        return run_job(working_dir, args.id)

    print("error: unknown schedule subcommand", file=sys.stderr)
    return 1


def _schedule_opts_from_args(args: argparse.Namespace) -> tuple[str | None, str, str]:
    """Extract schedule type, value, and start_at from args."""
    start_at = getattr(args, "start", None) or ""
    if getattr(args, "at", None):
        if start_at:
            print("warning: --start is ignored for --at (one-time schedules)", file=sys.stderr)
        return "once", args.at, ""
    if getattr(args, "every", None):
        return "every", args.every, start_at
    if getattr(args, "cron", None):
        return "cron", args.cron, start_at
    return None, "", ""


def _prompt_schedule_type() -> tuple[str | None, str, str]:
    """Interactively ask the user what kind of schedule they want."""
    print("How should this script run?\n")
    print("  1) Once at a specific time        (e.g. 2026-03-08T09:00)")
    print("  2) Repeating on an interval        (e.g. every 1h, 30m, 2d)")
    print("  3) On a cron schedule              (e.g. 0 9 * * *)")
    print()
    try:
        choice = input("Choice [1/2/3]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None, "", ""

    if choice == "1":
        try:
            value = input("Run at (ISO 8601 datetime, e.g. 2026-03-08T09:00): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None, "", ""
        return "once", value, ""
    if choice == "2":
        try:
            value = input("Repeat every (e.g. 30s, 5m, 1h, 2d): ").strip()
            start = input("First run at (ISO 8601, e.g. 2026-03-08T09:00 — Enter for now): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None, "", ""
        return "every", value, start
    if choice == "3":
        try:
            value = input("Cron expression (5 fields, e.g. 0 9 * * *): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None, "", ""
        return "cron", value, ""

    print("Invalid choice.", file=sys.stderr)
    return None, "", ""


def _print_schedule_help() -> None:
    """Print a friendly guide for the schedule command."""
    print(
        "Schedule Lumon scripts to run automatically.\n"
        "\n"
        "Examples:\n"
        "\n"
        "  # Run a script every hour\n"
        "  lumon schedule add scripts/report.lumon --every 1h\n"
        "\n"
        "  # Run every hour, starting tomorrow at 9am\n"
        "  lumon schedule add scripts/report.lumon --every 1h --start 2026-03-09T09:00\n"
        "\n"
        "  # Run daily at 9am\n"
        "  lumon schedule add scripts/daily.lumon --cron '0 9 * * *'\n"
        "\n"
        "  # Run once at a specific time\n"
        "  lumon schedule add scripts/migrate.lumon --at 2026-03-08T09:00\n"
        "\n"
        "  # Interactive — prompts you for the schedule\n"
        "  lumon schedule add scripts/report.lumon\n"
        "\n"
        "  # List all scheduled jobs\n"
        "  lumon schedule list\n"
        "\n"
        "  # View logs for a job\n"
        "  lumon schedule logs sched_01\n"
        "\n"
        "  # Change a job's schedule\n"
        "  lumon schedule edit sched_01 --every 2h\n"
        "\n"
        "  # Remove a job\n"
        "  lumon schedule remove sched_01\n"
    )
