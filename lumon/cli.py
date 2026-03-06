"""Lumon CLI — entry point for the `lumon` command."""

from __future__ import annotations

import argparse
import importlib.resources
import json
import os
import sys
from pathlib import Path

from lumon import __version__
from lumon.ast_nodes import TestBlock
from lumon.backends import RealFS, RealGit
from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import LumonError, ReturnSignal
from lumon.evaluator import eval_node
from lumon.interpreter import _setup_loader, _setup_plugins, interpret
from lumon.parser import parse
from lumon.plugins import disk_manifest_namespaces, load_config, split_contracts
from lumon.serializer import deserialize
from lumon.source_utils import extract_blocks
from lumon.type_checker import type_check

_STATE_FILE = Path(".lumon_state.json")

_SUBCOMMANDS = {"deploy", "browse", "test", "respond", "spec", "version"}


# ---------------------------------------------------------------------------
# State helpers (for ask/spawn replay)
# ---------------------------------------------------------------------------


def _save_state(code: str, responses: list[object], batch_size: int = 0) -> None:
    _STATE_FILE.write_text(
        json.dumps({"code": code, "responses": responses, "batch_size": batch_size}, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_state() -> dict | None:
    if not _STATE_FILE.exists():
        return None
    return json.loads(_STATE_FILE.read_text(encoding="utf-8"))


def _batch_size_from_result(result: dict) -> int:
    """Extract spawn batch size from an interpreter result."""
    if result.get("type") != "spawn_batch":
        return 0
    spawns = result.get("spawns")
    if isinstance(spawns, list):
        return len(spawns)
    return 1


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


def cmd_run_code(code: str) -> int:
    """Execute Lumon code and print the JSON result to stdout."""
    state = _load_state()
    if state is not None and state.get("code") == code:
        # Resuming the same code — shouldn't happen via cmd_run, but be safe
        responses: list[object] = [deserialize(r) for r in state.get("responses", [])]
    else:
        responses = []

    io_backend = RealFS(".")
    git_backend = RealGit(".")
    result = interpret(
        code,
        io_backend=io_backend,
        git_backend=git_backend,
        responses=responses if responses else None,
        working_dir=".",
        persist=True,
    )
    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") in ("ask", "spawn_batch"):
        _save_state(code, [], batch_size=_batch_size_from_result(result))
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

    batch_size = state.get("batch_size", 0)
    prev_responses: list[object] = [deserialize(r) for r in state.get("responses", [])]

    if batch_size > 1 and isinstance(response_raw, list) and len(response_raw) == batch_size:
        new_responses = [deserialize(r) for r in response_raw]
        responses = prev_responses + new_responses
    elif batch_size > 1 and isinstance(response_raw, dict):
        # Dict keyed by spawn_0, spawn_1, ... — distribute to each spawn
        if all(f"spawn_{i}" in response_raw for i in range(batch_size)):
            new_responses = [deserialize(response_raw[f"spawn_{i}"]) for i in range(batch_size)]
            responses = prev_responses + new_responses
        else:
            response = deserialize(response_raw)
            responses = prev_responses + [response]
    else:
        response = deserialize(response_raw)
        responses = prev_responses + [response]

    io_backend = RealFS(".")
    git_backend = RealGit(".")
    result = interpret(
        state["code"],
        io_backend=io_backend,
        git_backend=git_backend,
        responses=responses,
        working_dir=".",
    )
    print(json.dumps(result, ensure_ascii=False))

    if result.get("type") in ("ask", "spawn_batch"):
        _save_state(
            state["code"],
            [json.loads(json.dumps(r)) for r in responses],
            batch_size=_batch_size_from_result(result),
        )
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
    else:
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
            type_check(ast)
            env = Environment()
            register_builtins(env, None, None)
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
                        test_env = env.child_scope()
                        for stmt in test.body:
                            eval_node(stmt, test_env)
                        print(f"  PASS  {test.name}")
                        passed += 1
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
) -> None:
    """Deploy a single file with conflict detection."""
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if existing == content:
            return  # identical — skip silently
        if force or _prompt_overwrite(rel):
            dest.write_text(content, encoding="utf-8")
            deployed.append(rel)
        else:
            skipped.append(rel)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        deployed.append(rel)


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
    plugins_dir = target / "plugins"
    plugins_dir.mkdir(exist_ok=True)

    files = _deploy_files()
    deployed: list[str] = []
    skipped: list[str] = []

    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    for filename, content in files.items():
        if filename == "CLAUDE.md":
            dest = target / filename
        elif filename == "plugin-CLAUDE.md":
            dest = plugins_dir / "CLAUDE.md"
        elif filename.endswith(".py"):
            dest = hooks_dir / filename
        else:
            dest = claude_dir / filename
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped)

    # Deploy skills
    skills = _deploy_skills()
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir(exist_ok=True)

    for skill_name, content in sorted(skills.items()):
        skill_dir = skills_dir / skill_name
        skill_dir.mkdir(exist_ok=True)
        dest = skill_dir / "SKILL.md"
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped)

    # Deploy plugin skills
    plugin_skills = _deploy_plugin_skills()
    plugin_skills_dir = plugins_dir / ".claude" / "skills"
    plugin_skills_dir.mkdir(parents=True, exist_ok=True)

    for skill_name, content in sorted(plugin_skills.items()):
        skill_dir = plugin_skills_dir / skill_name
        skill_dir.mkdir(exist_ok=True)
        dest = skill_dir / "SKILL.md"
        rel = str(dest.relative_to(target))
        _deploy_file(dest, content, rel, args.force, deployed, skipped)

    # Create starter .lumon.json at target root
    lumon_json = target / ".lumon.json"
    starter = json.dumps({"plugins": {}}, indent=2) + "\n"
    _deploy_file(lumon_json, starter, ".lumon.json", args.force, deployed, skipped)

    if deployed:
        print(f"Deployed to {target}:")
        for f in deployed:
            print(f"  + {f}")

    if skipped:
        print(f"\nSkipped (differ — use --force to overwrite):")
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
        if "\n" in arg or len(arg) > 255:
            code = arg
        else:
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
