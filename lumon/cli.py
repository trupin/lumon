"""Lumon CLI — entry point for the `lumon` command."""

from __future__ import annotations

import argparse
import importlib.resources
import json
import os
import signal
import sys
from pathlib import Path

from lumon import __version__
from lumon.cli_schedule import cmd_schedule
from lumon.ast_nodes import TestBlock
from lumon.backends import MemoryFS, MemoryGit, RealFS, RealGit
from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal
from lumon.evaluator import eval_node
from lumon.daemon import (
    SuspendEvent,
    cleanup_stale_sessions,
    is_daemon_alive,
    read_daemon_output,
    run_with_daemon,
)
from lumon.interpreter import (
    _setup_loader,
    _setup_plugins,
    cleanup_comm_dir,
    generate_session_id,
    interpret_with_suspend,
)
from lumon.parser import parse
from lumon.plugins import disk_manifest_namespaces, load_config, split_contracts
from lumon.source_utils import extract_blocks
from lumon.type_checker import type_check

_COMM_BASE = ".lumon_comm"

_SUBCOMMANDS = {"deploy", "browse", "test", "respond", "spec", "version", "schedule"}


# ---------------------------------------------------------------------------
# Session helpers (daemon model)
# ---------------------------------------------------------------------------


def _comm_dir_for_session(session: str) -> str:
    """Return the comm directory path for a session."""
    return os.path.join(_COMM_BASE, session)


def _save_script_marker(comm_dir: str, script: str) -> None:
    """Save a script marker file so we can detect pending sessions for a script."""
    os.makedirs(comm_dir, exist_ok=True)
    marker_file = os.path.join(comm_dir, "script.txt")
    with open(marker_file, "w", encoding="utf-8") as f:
        f.write(script)


def _find_session() -> str | None:
    """Find the single active session, if any."""
    if not os.path.isdir(_COMM_BASE):
        return None
    sessions = [
        d for d in os.listdir(_COMM_BASE)
        if os.path.isdir(os.path.join(_COMM_BASE, d))
    ]
    if len(sessions) == 1:
        return sessions[0]
    return None


def _clear_state(session: str) -> None:
    """Remove a session directory (kill daemon if alive)."""
    comm_dir = _comm_dir_for_session(session)
    # Try to kill daemon process
    pid_file = os.path.join(comm_dir, "pid")
    if os.path.isfile(pid_file):
        try:
            with open(pid_file, encoding="utf-8") as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGKILL)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
    cleanup_comm_dir(comm_dir)


def _find_pending_daemon(script: str) -> str | None:
    """Find a pending daemon session associated with the given script path."""
    if not os.path.isdir(_COMM_BASE):
        return None
    for name in os.listdir(_COMM_BASE):
        session_dir = os.path.join(_COMM_BASE, name)
        if not os.path.isdir(session_dir):
            continue
        marker_file = os.path.join(session_dir, "script.txt")
        if not os.path.isfile(marker_file):
            continue
        with open(marker_file, encoding="utf-8") as f:
            saved_script = f.read().strip()
        if saved_script == script and is_daemon_alive(session_dir):
            return name
    return None


# ---------------------------------------------------------------------------
# Deploy helpers
# ---------------------------------------------------------------------------


def _deploy_files() -> dict[str, str]:
    """Return {filename: text_content} for all bundled deploy templates."""
    pkg = importlib.resources.files("lumon._deploy")
    result: dict[str, str] = {}
    for name in ("CLAUDE.md", "settings.json", "sandbox-guard.py", "plugin-CLAUDE.md"):
        result[name] = (pkg / name).read_text(encoding="utf-8")
    return result


def _deploy_skills() -> dict[str, str]:
    """Return {skill_name: SKILL.md content} for all bundled deploy skills."""
    pkg = importlib.resources.files("lumon._deploy.skills")
    result: dict[str, str] = {}
    # Iterate over skill directories
    for item in pkg.iterdir():
        skill_file = item / "SKILL.md"
        if skill_file.is_file():
            result[item.name] = skill_file.read_text(encoding="utf-8")
    return result


def _deploy_plugin_skills() -> dict[str, str]:
    """Return {skill_name: SKILL.md content} for all bundled plugin skills."""
    pkg = importlib.resources.files("lumon._deploy.plugin_skills")
    result: dict[str, str] = {}
    for item in pkg.iterdir():
        skill_file = item / "SKILL.md"
        if skill_file.is_file():
            result[item.name] = skill_file.read_text(encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_version() -> int:
    """Print the Lumon version."""
    print(f"lumon {__version__}")
    return 0


def cmd_spec(_args: argparse.Namespace) -> int:
    """Print the Lumon language specification."""
    text = importlib.resources.files("lumon._spec").joinpath("spec.md").read_text(encoding="utf-8")
    print(text, end="")
    return 0


def cmd_run_code(code: str, *, script: str | None = None) -> int:
    """Execute Lumon code and print the JSON result to stdout.

    Uses the persistent daemon model: on suspension, forks a child process
    that stays alive and polls for response files. The parent prints the
    suspension envelope and exits.
    """
    # Block re-run if the same script already has a pending daemon session
    if script:
        pending = _find_pending_daemon(script)
        if pending:
            msg = (
                f"Script has pending session {pending}. "
                f"Use 'lumon respond' to resume or 'lumon respond --clear' to discard."
            )
            result: dict[str, object] = {"type": "error", "message": msg}
            print(json.dumps(result, ensure_ascii=False))
            return 1

    # Clean up stale daemon sessions
    cleanup_stale_sessions(_COMM_BASE)

    session = generate_session_id()
    comm_dir = _comm_dir_for_session(session)

    io_backend = RealFS(".")
    git_backend = RealGit(_project_root or ".")

    def run_fn(suspend: SuspendEvent) -> dict:
        return interpret_with_suspend(
            code,
            io_backend=io_backend,
            git_backend=git_backend,
            working_dir=".",
            persist=True,
            comm_dir=comm_dir,
            suspend_event=suspend,
        )

    result = run_with_daemon(run_fn, comm_dir, session)

    # Save script association for pending session detection
    if result.get("type") in ("ask", "spawn_batch") and script:
        _save_script_marker(comm_dir, script)

    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") not in ("ask", "spawn_batch"):
        # No suspension — clean up comm dir
        cleanup_comm_dir(comm_dir)

    return 0 if result.get("type") != "error" else 1


def cmd_respond(args: argparse.Namespace) -> int:
    """Resume suspended execution by reading output from the daemon process."""
    session: str | None = getattr(args, "session", None)

    # Auto-detect session if not provided
    if not session:
        session = _find_session()

    # Handle --clear before checking for daemon
    if getattr(args, "clear", False):
        if not session:
            print("error: no pending session to clear", file=sys.stderr)
            return 1
        _clear_state(session)
        print(json.dumps({"type": "result", "value": f"Session {session} cleared."}))
        return 0

    if not session:
        print(
            "error: no suspended execution — run some Lumon code first",
            file=sys.stderr,
        )
        return 1

    comm_dir = _comm_dir_for_session(session)

    if not os.path.isdir(comm_dir):
        print(
            f"error: no session directory for '{session}'",
            file=sys.stderr,
        )
        return 1

    # Check if daemon is alive
    if not is_daemon_alive(comm_dir):
        print(
            f"error: daemon for session '{session}' is not running (process died). "
            f"Re-run the script to start a new session.",
            file=sys.stderr,
        )
        cleanup_comm_dir(comm_dir)
        return 1

    # Read output from daemon (polls for output.json)
    result = read_daemon_output(comm_dir, timeout=60)
    if result is None:
        print(
            f"error: timed out waiting for daemon output for session '{session}'",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") not in ("ask", "spawn_batch"):
        # Execution completed — clean up
        cleanup_comm_dir(comm_dir)

    return 0 if result.get("type") != "error" else 1


def _bundled_manifest(name: str) -> str | None:
    """Read a bundled manifest file from lumon._manifests, or None if missing."""
    pkg = importlib.resources.files("lumon._manifests")
    resource = pkg / name
    try:
        return resource.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        return None


def _annotate_manifest(manifest_text: str, contracts: dict) -> str:
    """Annotate manifest text: hide forced params, add contract annotations for dynamic ones."""
    if not contracts:
        return manifest_text

    # Flatten all param contracts across functions
    all_dynamic: dict[str, object] = {}
    all_forced_params: set[str] = set()
    for _fn_name, fn_contracts in contracts.items():
        if not isinstance(fn_contracts, dict):
            continue
        dynamic, forced = split_contracts(fn_contracts)
        all_dynamic.update(dynamic)
        all_forced_params.update(forced.keys())

    lines = manifest_text.splitlines()
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Check if this is a forced param line — hide it entirely
        skip = False
        for param_name in all_forced_params:
            if stripped.startswith(f"{param_name}:"):
                skip = True
                break
        if skip:
            continue
        # Annotate dynamic contract params
        for param_name, contract in all_dynamic.items():
            if stripped.startswith(f"{param_name}:"):
                annotation = _format_contract(contract)
                if annotation:
                    line = f"{line}  [contract: {annotation}]"
                break
        result.append(line)
    return "\n".join(result)


def _format_contract(contract: object) -> str:
    """Format a contract value for display."""
    if isinstance(contract, str):
        return contract
    if isinstance(contract, list):
        if len(contract) == 2 and all(isinstance(v, (int, float)) for v in contract):
            return f"{contract[0]}-{contract[1]}"
        if all(isinstance(v, str) for v in contract):
            return " | ".join(contract)
    return str(contract)


def _discover_plugin_namespaces() -> tuple[list[str], dict]:
    """Discover plugin namespaces from ../plugins/ based on .lumon.json.

    Supports multi-instance: config key is the alias, optional "plugin" key
    points to the source directory.
    Returns (list of alias names, config dict).
    """
    config = load_config(".")
    allowed = config.get("plugins", {})
    if not allowed:
        return [], config

    plugins_dir = os.path.normpath(os.path.join("..", "plugins"))
    if not os.path.isdir(plugins_dir):
        return [], config

    namespaces: list[str] = []
    for alias in sorted(allowed.keys()):
        instance_config = allowed[alias]
        source_name = alias
        if isinstance(instance_config, dict) and "plugin" in instance_config:
            source_name = instance_config["plugin"]
        plugin_path = os.path.join(plugins_dir, source_name)
        manifest_path = os.path.join(plugin_path, "manifest.lumon")
        if os.path.isdir(plugin_path) and os.path.isfile(manifest_path):
            namespaces.append(alias)
    return namespaces, config


def cmd_browse(args: argparse.Namespace) -> int:
    """Display the namespace index or a specific namespace manifest."""
    namespace: str | None = getattr(args, "namespace", None)

    if namespace:
        # Try disk first, then bundled manifests, then plugins
        path = Path("lumon") / "manifests" / f"{namespace}.lumon"
        if path.exists():
            # Check for plugin alias collision before returning disk manifest
            plugin_ns, _cfg = _discover_plugin_namespaces()
            if namespace in plugin_ns:
                print(
                    f"Namespace conflict: '{namespace}' is both a plugin alias "
                    f"and a disk manifest (lumon/manifests/{namespace}.lumon). "
                    f"Remove one to avoid ambiguity.",
                    file=sys.stderr,
                )
                return 1
            print(path.read_text(encoding="utf-8"), end="")
            return 0
        bundled = _bundled_manifest(f"{namespace}.lumon")
        if bundled is not None:
            print(bundled, end="")
            return 0
        # Check plugins (resolve source dir via "plugin" key)
        config = load_config(".")
        plugin_config = config.get("plugins", {})
        instance_config = plugin_config.get(namespace, {})
        source_name = namespace
        if isinstance(instance_config, dict) and "plugin" in instance_config:
            source_name = instance_config["plugin"]
        plugin_manifest = Path("..") / "plugins" / source_name / "manifest.lumon"
        if plugin_manifest.exists():
            text = plugin_manifest.read_text(encoding="utf-8")
            # Replace source namespace with alias in manifest text
            if source_name != namespace:
                text = text.replace(f"{source_name}.", f"{namespace}.")
            # Filter by expose list if present
            if isinstance(instance_config, dict) and "expose" in instance_config:
                expose_list = instance_config["expose"]
                if not isinstance(expose_list, list):
                    print(
                        f"error: 'expose' for plugin '{namespace}' must be a list",
                        file=sys.stderr,
                    )
                    return 1
                if isinstance(expose_list, list):
                    allowed = {namespace + "." + name for name in expose_list}
                    blocks = extract_blocks(text)
                    text = "\n\n".join(
                        src for btype, ns_path, src in blocks
                        if btype == "define" and ns_path in allowed
                    )
                    if text:
                        text += "\n"
            # Strip reserved keys and annotate contracts
            if isinstance(instance_config, dict):
                fn_contracts = {
                    k: v for k, v in instance_config.items()
                    if k not in {"plugin", "env", "expose"}
                }
                if fn_contracts:
                    text = _annotate_manifest(text, fn_contracts)
            print(text, end="")
            return 0
        print(f"error: manifest for '{namespace}' not found ({path})", file=sys.stderr)
        return 1

    # Index: show bundled index, then append user namespaces from disk, then plugins
    parts: list[str] = []
    bundled = _bundled_manifest("index.lumon")
    if bundled is not None:
        parts.append(bundled.rstrip("\n"))
    disk_index = Path("lumon") / "index.lumon"
    if disk_index.exists():
        parts.append(disk_index.read_text(encoding="utf-8").rstrip("\n"))
    # Append plugin namespaces (check for disk conflicts first)
    plugin_ns, _config = _discover_plugin_namespaces()
    disk_ns = disk_manifest_namespaces(".")
    for ns in plugin_ns:
        if ns in disk_ns:
            print(
                f"Namespace conflict: '{ns}' is both a plugin alias "
                f"and a disk manifest (lumon/manifests/{ns}.lumon). "
                f"Remove one to avoid ambiguity.",
                file=sys.stderr,
            )
            return 1
        parts.append(f"{ns} -- plugin")
    if not parts:
        print("error: namespace index not found (lumon/index.lumon)", file=sys.stderr)
        return 1
    print("\n".join(parts))
    return 0


def _register_test_builtins(
    env: Environment, test_fs: MemoryFS,
) -> dict[tuple[str, str], list[object]]:
    """Register mock_io, mock_ask, mock_spawn, mock_plugin builtins for test mode.

    Returns the plugin_mocks dict so callers can clear it between tests.
    """
    plugin_mocks: dict[tuple[str, str], list[object]] = {}

    def _mock_io(entries: list[dict]) -> None:
        files = {e["path"]: e["content"] for e in entries}
        test_fs.seed(files)

    def _mock_plugin_executor(
        command: str, _args_map: dict[str, object],
        _plugin_dir: str, instance: str,
    ) -> object:
        key = (instance, command)
        if key not in plugin_mocks or not plugin_mocks[key]:
            raise LumonError(
                f"No mock registered for plugin ({instance}, {command})"
            )
        return plugin_mocks[key].pop(0)

    def _mock_plugin(ns: str, command: str, response: object) -> None:
        plugin_mocks.setdefault((ns, command), []).append(response)

    def _mock_ask(response: object) -> None:
        env._response_queue.append(response)

    def _mock_spawn(responses: list[object]) -> None:
        env._response_queue.extend(responses)

    env.register_builtin("mock_io", _mock_io)
    env._plugin_executor = _mock_plugin_executor
    env.register_builtin("mock_plugin", _mock_plugin)
    env.register_builtin("mock_ask", _mock_ask)
    env.register_builtin("mock_spawn", _mock_spawn)
    return plugin_mocks


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

        try:
            ast = parse(code)
            type_check(ast, io_backend=True, git_backend=True, test_mode=True)
            test_fs = MemoryFS(root="/sandbox")
            test_git = MemoryGit()
            env = Environment()
            register_builtins(env, test_fs, test_git)
            plugin_mocks = _register_test_builtins(env, test_fs)

            env._working_dir = "."
            _setup_loader(env, ".")
            _setup_plugins(env, ".")

            # Evaluate top-level to register defines, implements, and tests
            try:
                eval_node(ast, env)
            except ReturnSignal:
                pass

            tests = env.get_tests()
            if tests:
                # Run each test block individually
                for test in tests:
                    assert isinstance(test, TestBlock)
                    try:
                        test_fs.clear()
                        plugin_mocks.clear()
                        env._response_queue.clear()
                        env._pending_spawns.clear()
                        env._spawn_counter[0] = 0
                        test_env = env.child_scope()
                        for stmt in test.body:
                            eval_node(stmt, test_env)
                        print(f"  PASS  {test.name}")
                        passed += 1
                    except AskSignal:
                        print(f"  FAIL  {test.name}: ask expression reached without mock_ask")
                        failed += 1
                    except (LumonError, ReturnSignal) as e:
                        msg = str(e) if isinstance(e, LumonError) else "unexpected return"
                        print(f"  FAIL  {test.name}: {msg}")
                        failed += 1
            else:
                # No test blocks — treat the whole file as a single test (legacy)
                print(f"  PASS  {f.stem}")
                passed += 1

        except LumonError as e:
            print(f"  FAIL  {f.stem}: {e}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} passed")
    return 0 if failed == 0 else 1



def _prompt_overwrite(rel_path: str) -> bool:
    """Ask the user whether to overwrite a file that differs from the bundled version."""
    try:
        answer = input(f"  '{rel_path}' differs from bundled version. Overwrite? [y/N] ")
        return answer.strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def _deploy_file(
    dest: Path,
    content: str,
    rel: str,
    force: bool,
    deployed: list[str],
    skipped: list[str],
    *,
    dry_run: bool = False,
) -> None:
    """Deploy a single file with conflict detection."""
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if existing == content:
            return  # identical — skip silently
        if dry_run:
            skipped.append(rel)
            return
        if force or _prompt_overwrite(rel):
            dest.write_text(content, encoding="utf-8")
            deployed.append(rel)
        else:
            skipped.append(rel)
    else:
        if dry_run:
            deployed.append(rel)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        deployed.append(rel)


def cmd_deploy(args: argparse.Namespace) -> int:
    """Copy the bundled Claude Code agent config to a target directory."""
    target = Path(args.target).expanduser().resolve()
    claude_dir = target / ".claude"
    dry_run: bool = getattr(args, "dry_run", False)

    if not target.exists():
        print(f"error: target path does not exist: {target}", file=sys.stderr)
        return 1

    if not dry_run:
        claude_dir.mkdir(exist_ok=True)
        (target / "sandbox").mkdir(exist_ok=True)
        (target / "plugins").mkdir(exist_ok=True)

    plugins_dir = target / "plugins"
    files = _deploy_files()
    deployed: list[str] = []
    skipped: list[str] = []

    if not dry_run:
        (claude_dir / "hooks").mkdir(exist_ok=True)

    for filename, content in files.items():
        if filename == "CLAUDE.md":
            dest = target / filename
        elif filename == "plugin-CLAUDE.md":
            dest = plugins_dir / "CLAUDE.md"
        elif filename.endswith(".py"):
            dest = (claude_dir / "hooks") / filename
        else:
            dest = claude_dir / filename
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped, dry_run=dry_run)

    # Deploy skills
    skills = _deploy_skills()
    skills_dir = claude_dir / "skills"
    if not dry_run:
        skills_dir.mkdir(exist_ok=True)

    for skill_name, content in sorted(skills.items()):
        skill_dir = skills_dir / skill_name
        if not dry_run:
            skill_dir.mkdir(exist_ok=True)
        dest = skill_dir / "SKILL.md"
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped, dry_run=dry_run)

    # Deploy plugin skills
    plugin_skills = _deploy_plugin_skills()
    plugin_skills_dir = plugins_dir / ".claude" / "skills"
    if not dry_run:
        plugin_skills_dir.mkdir(parents=True, exist_ok=True)

    for skill_name, content in sorted(plugin_skills.items()):
        skill_dir = plugin_skills_dir / skill_name
        if not dry_run:
            skill_dir.mkdir(exist_ok=True)
        dest = skill_dir / "SKILL.md"
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped, dry_run=dry_run)

    # Create starter .lumon.json at target root (only if it doesn't exist —
    # this file contains user config and must never be overwritten).
    lumon_json = target / ".lumon.json"
    if not lumon_json.exists():
        starter = json.dumps({"plugins": {}}, indent=2) + "\n"
        _deploy_file(lumon_json, starter, ".lumon.json", args.force, deployed, skipped, dry_run=dry_run)

    label = "Dry run for" if dry_run else "Deployed to"
    if deployed:
        print(f"{label} {target}:")
        for f in deployed:
            print(f"  + {f}" if not dry_run else f"  + {f} (new)")

    if skipped:
        if dry_run:
            print("\nWould update (differ from bundled version):")
        else:
            print("\nSkipped (differ — use --force to overwrite):")
        for f in skipped:
            print(f"  ~ {f}")

    if not deployed and not skipped:
        print("Nothing to deploy — already up to date.")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


_project_root: str = ""


def _apply_working_dir() -> None:
    """Extract and apply --working-dir before argparse runs.

    Saves the original directory as *_project_root* so that git commands
    run from the project root rather than the sandbox.
    """
    global _project_root  # noqa: PLW0603
    _project_root = os.getcwd()
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
        script: str | None = None
        if "\n" in arg or len(arg) > 255:
            code = arg
        else:
            path = Path(arg)
            if path.exists() and path.suffix == ".lumon":
                code = path.read_text(encoding="utf-8")
                script = str(path)
            else:
                code = arg
        sys.exit(cmd_run_code(code, script=script))

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
    elif args.command == "schedule":
        sys.exit(cmd_schedule(args))
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
            "Respond:     lumon respond [<session>]\n"
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
            "Resume a suspended Lumon execution by reading response files\n"
            "from .lumon_comm/<session>/. The session ID is auto-detected\n"
            "if there is exactly one active session."
        ),
    )
    p_respond.add_argument(
        "session",
        nargs="?",
        default=None,
        help="Session ID to respond to (auto-detected if omitted).",
    )
    p_respond.add_argument(
        "--clear",
        action="store_true",
        help="Discard a pending session instead of resuming it.",
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
    p_deploy.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without making changes.",
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

    # schedule
    p_schedule = sub.add_parser(
        "schedule",
        help="Manage scheduled execution of Lumon scripts.",
        description="Schedule Lumon scripts to run at specific times or on recurring intervals via launchd.",
    )
    sched_sub = p_schedule.add_subparsers(dest="schedule_command", metavar="<subcommand>")

    # schedule add
    p_sched_add = sched_sub.add_parser("add", help="Create a new scheduled job.")
    p_sched_add.add_argument("file", help="Path to the Lumon script to schedule.")
    sched_add_group = p_sched_add.add_mutually_exclusive_group()
    sched_add_group.add_argument("--at", help="One-time execution (ISO 8601 datetime, e.g. 2026-03-08T09:00).")
    sched_add_group.add_argument("--every", help="Recurring interval (e.g. 30s, 5m, 1h, 2d).")
    sched_add_group.add_argument("--cron", help="Cron expression (5 fields, e.g. '0 9 * * *').")
    p_sched_add.add_argument(
        "--start",
        help="First run time for --every schedules (ISO 8601 datetime). Runs are skipped until this time.",
    )

    # schedule list
    sched_sub.add_parser("list", help="Show all scheduled jobs.")

    # schedule edit
    p_sched_edit = sched_sub.add_parser("edit", help="Modify an existing job's schedule.")
    p_sched_edit.add_argument("id", help="Job ID (e.g. sched_01).")
    sched_edit_group = p_sched_edit.add_mutually_exclusive_group()
    sched_edit_group.add_argument("--at", help="One-time execution (ISO 8601 datetime).")
    sched_edit_group.add_argument("--every", help="Recurring interval (e.g. 30s, 5m, 1h, 2d).")
    sched_edit_group.add_argument("--cron", help="Cron expression (5 fields).")
    p_sched_edit.add_argument("--start", help="First run time for --every schedules (ISO 8601 datetime).")

    # schedule remove
    p_sched_remove = sched_sub.add_parser("remove", help="Delete a scheduled job.")
    p_sched_remove.add_argument("id", help="Job ID (e.g. sched_01).")

    # schedule logs
    p_sched_logs = sched_sub.add_parser("logs", help="Show execution history for a job.")
    p_sched_logs.add_argument("id", help="Job ID (e.g. sched_01).")
    p_sched_logs.add_argument("--limit", type=int, default=10, help="Number of log entries to show (default: 10).")

    # schedule _run (internal — called by launchd)
    p_sched_run = sched_sub.add_parser("_run", help=argparse.SUPPRESS)
    p_sched_run.add_argument("id", help="Job ID.")

    return parser


if __name__ == "__main__":
    main()
