"""Lumon CLI — entry point for the `lumon` command."""

from __future__ import annotations

import argparse
import importlib.resources
import json
import os
import sys
from pathlib import Path

from lumon import __version__
from lumon.backends import RealFS
from lumon.interpreter import interpret
from lumon.serializer import deserialize

_STATE_FILE = Path(".lumon_state.json")

_SUBCOMMANDS = {"deploy", "browse", "test", "respond", "spec", "version"}


# ---------------------------------------------------------------------------
# State helpers (for ask/spawn replay)
# ---------------------------------------------------------------------------


def _save_state(code: str, responses: list[object]) -> None:
    _STATE_FILE.write_text(
        json.dumps({"code": code, "responses": responses}, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_state() -> dict | None:
    if not _STATE_FILE.exists():
        return None
    return json.loads(_STATE_FILE.read_text(encoding="utf-8"))


def _clear_state() -> None:
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()


# ---------------------------------------------------------------------------
# Deploy helpers
# ---------------------------------------------------------------------------


def _deploy_files() -> dict[str, str]:
    """Return {filename: text_content} for all bundled deploy templates."""
    pkg = importlib.resources.files("lumon._deploy")
    result: dict[str, str] = {}
    for name in ("CLAUDE.md", "settings.json", "sandbox-guard.py"):
        result[name] = (pkg / name).read_text(encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_version() -> int:
    """Print the Lumon version."""
    print(f"lumon {__version__}")
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    """Print the Lumon language specification."""
    text = importlib.resources.files("lumon._spec").joinpath("spec.md").read_text(encoding="utf-8")
    print(text, end="")
    return 0


def cmd_run_code(code: str) -> int:
    """Execute Lumon code and print the JSON result to stdout."""
    state = _load_state()
    if state is not None and state.get("code") == code:
        # Resuming the same code — shouldn't happen via cmd_run, but be safe
        responses: list[object] = [deserialize(r) for r in state.get("responses", [])]
    else:
        responses = []

    io_backend = RealFS(".")
    result = interpret(
        code,
        io_backend=io_backend,
        responses=responses if responses else None,
        working_dir=".",
        persist=True,
    )
    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") in ("ask", "spawn_batch"):
        _save_state(code, [])
    else:
        _clear_state()

    return 0 if result.get("type") != "error" else 1


def cmd_respond(args: argparse.Namespace) -> int:
    """Resume suspended execution by feeding a response."""
    state = _load_state()
    if state is None:
        print(
            "error: no suspended execution — run some Lumon code first",
            file=sys.stderr,
        )
        return 1

    try:
        response_raw = json.loads(args.response)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1

    response = deserialize(response_raw)
    prev_responses: list[object] = [deserialize(r) for r in state.get("responses", [])]
    responses = prev_responses + [response]

    result = interpret(state["code"], responses=responses, working_dir=".")
    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") in ("ask", "spawn_batch"):
        _save_state(state["code"], [json.loads(json.dumps(r)) for r in responses])
    else:
        _clear_state()

    return 0 if result.get("type") != "error" else 1


def _bundled_manifest(name: str) -> str | None:
    """Read a bundled manifest file from lumon._manifests, or None if missing."""
    pkg = importlib.resources.files("lumon._manifests")
    resource = pkg / name
    try:
        return resource.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        return None


def cmd_browse(args: argparse.Namespace) -> int:
    """Display the namespace index or a specific namespace manifest."""
    namespace: str | None = getattr(args, "namespace", None)

    if namespace:
        # Try disk first, then bundled manifests
        path = Path("lumon") / "manifests" / f"{namespace}.lumon"
        if path.exists():
            print(path.read_text(encoding="utf-8"), end="")
            return 0
        bundled = _bundled_manifest(f"{namespace}.lumon")
        if bundled is not None:
            print(bundled, end="")
            return 0
        print(f"error: manifest for '{namespace}' not found ({path})", file=sys.stderr)
        return 1
    else:
        # Index: show bundled index, then append user namespaces from disk
        parts: list[str] = []
        bundled = _bundled_manifest("index.lumon")
        if bundled is not None:
            parts.append(bundled.rstrip("\n"))
        disk_index = Path("lumon") / "index.lumon"
        if disk_index.exists():
            parts.append(disk_index.read_text(encoding="utf-8").rstrip("\n"))
        if not parts:
            print("error: namespace index not found (lumon/index.lumon)", file=sys.stderr)
            return 1
        print("\n".join(parts))
        return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Run Lumon test files and report results."""
    namespace: str | None = getattr(args, "namespace", None)
    test_dir = Path("lumon") / "tests"

    if namespace:
        files = [test_dir / f"{namespace}.lumon"]
    else:
        if not test_dir.exists():
            print("No tests found (lumon/tests/ does not exist).")
            return 0
        files = sorted(test_dir.glob("*.lumon"))

    if not files:
        print("No tests found.")
        return 0

    passed = 0
    failed = 0

    for f in files:
        if not f.exists():
            print(f"  SKIP  {f.stem} (file not found)")
            continue
        code = f.read_text(encoding="utf-8")
        result = interpret(code, working_dir=".")
        if result.get("type") == "error":
            print(f"  FAIL  {f.stem}: {result.get('message', 'unknown error')}")
            failed += 1
        else:
            print(f"  PASS  {f.stem}")
            passed += 1

    total = passed + failed
    print(f"\n{passed}/{total} passed")
    return 0 if failed == 0 else 1


def cmd_deploy(args: argparse.Namespace) -> int:
    """Copy the bundled Claude Code agent config to a target directory."""
    target = Path(args.target).expanduser().resolve()
    claude_dir = target / ".claude"

    if not target.exists():
        print(f"error: target path does not exist: {target}", file=sys.stderr)
        return 1

    claude_dir.mkdir(exist_ok=True)
    sandbox_dir = target / "sandbox"
    sandbox_dir.mkdir(exist_ok=True)

    files = _deploy_files()
    deployed: list[str] = []
    skipped: list[str] = []

    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    for filename, content in files.items():
        # CLAUDE.md → project root, hooks → .claude/hooks/, rest → .claude/
        if filename == "CLAUDE.md":
            dest = target / filename
        elif filename.endswith(".py"):
            dest = hooks_dir / filename
        else:
            dest = claude_dir / filename
        if dest.exists() and not args.force:
            skipped.append(str(dest.relative_to(target)))
            continue
        dest.write_text(content, encoding="utf-8")
        deployed.append(str(dest.relative_to(target)))

    if deployed:
        print(f"Deployed to {target}:")
        for f in deployed:
            print(f"  + {f}")

    if skipped:
        print(f"\nSkipped (already exist — use --force to overwrite):")
        for f in skipped:
            print(f"  ~ {f}")

    if not deployed and not skipped:
        print("Nothing to deploy.")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _apply_working_dir() -> None:
    """Extract and apply --working-dir before argparse runs."""
    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg == "--working-dir" and i + 1 < len(sys.argv):
            wd = sys.argv[i + 1]
            os.chdir(wd)
            del sys.argv[i : i + 2]
            return
        if arg.startswith("--working-dir="):
            wd = arg.split("=", 1)[1]
            os.chdir(wd)
            del sys.argv[i]
            return


def main() -> None:
    # Handle --working-dir before anything else (including the fast path).
    _apply_working_dir()

    # Fast path: if first arg is not a known subcommand, treat it as code/file.
    if len(sys.argv) == 1:
        # No args: read from stdin
        if not sys.stdin.isatty():
            code = sys.stdin.read()
            sys.exit(cmd_run_code(code))
        else:
            _build_parser().print_help()
            sys.exit(0)

    if sys.argv[1] not in _SUBCOMMANDS and not sys.argv[1].startswith("-"):
        # Positional arg: inline code or a file path
        arg = sys.argv[1]
        path = Path(arg)
        if path.exists() and path.suffix == ".lumon":
            code = path.read_text(encoding="utf-8")
        else:
            code = arg
        sys.exit(cmd_run_code(code))

    # Subcommand dispatch via argparse
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "browse":
        sys.exit(cmd_browse(args))
    elif args.command == "test":
        sys.exit(cmd_test(args))
    elif args.command == "respond":
        sys.exit(cmd_respond(args))
    elif args.command == "deploy":
        sys.exit(cmd_deploy(args))
    elif args.command == "spec":
        sys.exit(cmd_spec(args))
    elif args.command == "version":
        sys.exit(cmd_version())
    else:
        parser.print_help()
        sys.exit(0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lumon",
        description=(
            "Lumon language interpreter and tooling.\n\n"
            "Run code:    lumon 'return 42'\n"
            "From file:   lumon impl/inbox.lumon\n"
            "From stdin:  echo 'return 42' | lumon\n"
            "Browse:      lumon browse [<namespace>]\n"
            "Test:        lumon test [<namespace>]\n"
            "Respond:     lumon respond '<json>'\n"
            "Deploy:      lumon deploy <target>\n"
            "Spec:        lumon spec"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--working-dir",
        metavar="<path>",
        help="Use <path> as the base directory (applied before any command).",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # browse
    p_browse = sub.add_parser(
        "browse",
        help="Show namespace index or a specific namespace manifest.",
        description="Display the namespace index (lumon/index.lumon) or a specific manifest.",
    )
    p_browse.add_argument(
        "namespace",
        nargs="?",
        help="Namespace to show (e.g. 'inbox'). Omit to show the full index.",
    )

    # test
    p_test = sub.add_parser(
        "test",
        help="Run Lumon test files.",
        description="Run test files from lumon/tests/. Pass a namespace to run only that file.",
    )
    p_test.add_argument(
        "namespace",
        nargs="?",
        help="Namespace to test (e.g. 'inbox'). Omit to run all tests.",
    )

    # respond
    p_respond = sub.add_parser(
        "respond",
        help="Resume suspended execution (after ask/spawn).",
        description=(
            "Feed a JSON response back to a suspended Lumon execution.\n"
            "The state is loaded from .lumon_state.json in the current directory."
        ),
    )
    p_respond.add_argument(
        "response",
        help="JSON value to feed back (e.g. '{\"action\": \"process\"}').",
    )

    # deploy
    p_deploy = sub.add_parser(
        "deploy",
        help="Deploy the Claude Code agent configuration to a target directory.",
        description=(
            "Copy the locked-down Claude Code configuration (CLAUDE.md, settings.json) "
            "into <target>/.claude/, making that directory ready for a Lumon agent to run."
        ),
    )
    p_deploy.add_argument(
        "target",
        help="Directory where the agent will run (e.g. ~/my-project).",
    )
    p_deploy.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    # spec
    sub.add_parser(
        "spec",
        help="Print the Lumon language specification.",
        description="Print the full Lumon language specification to stdout.",
    )

    # version
    sub.add_parser(
        "version",
        help="Print the Lumon version.",
    )

    return parser


if __name__ == "__main__":
    main()
