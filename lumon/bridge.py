"""Bridge system: maps define signatures to external executables via JSON stdin/stdout."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Callable

from lumon.errors import LumonError
from lumon.serializer import deserialize
from lumon.values import LumonTag


def parse_bridges(source: str) -> dict[str, str]:
    """Parse a bridges.lumon config file into {name: run_cmd} pairs.

    Format:
        bridge browser.search
          run: "python3 plugins/search.py"
    """
    bridges: dict[str, str] = {}
    current_name: str | None = None

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue

        if stripped.startswith("bridge "):
            current_name = stripped[len("bridge "):].strip()
            if not current_name:
                raise LumonError("Invalid bridge declaration: missing function name")
        elif stripped.startswith("run:") and current_name is not None:
            run_value = stripped[len("run:"):].strip()
            # Strip surrounding quotes
            if len(run_value) >= 2 and run_value[0] == '"' and run_value[-1] == '"':
                run_value = run_value[1:-1]
            if not run_value:
                raise LumonError(f"Invalid bridge '{current_name}': missing run command")
            bridges[current_name] = run_value
            current_name = None
        elif current_name is not None and stripped:
            raise LumonError(f"Invalid bridge '{current_name}': expected 'run:' directive")

    if current_name is not None:
        raise LumonError(f"Incomplete bridge declaration: '{current_name}' missing 'run:' directive")

    return bridges


def load_bridges(working_dir: str) -> dict[str, str]:
    """Read lumon/bridges.lumon from disk. Returns {} if file doesn't exist."""
    path = os.path.join(working_dir, "lumon", "bridges.lumon")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return parse_bridges(source)


BridgeExecutor = Callable[[str, dict[str, object], str, str], object]
"""Signature: (name, args_dict, run_cmd, working_dir) -> result value."""


def call_bridge(
    name: str,
    args: dict[str, object],
    run_cmd: str,
    working_dir: str,
    executor: BridgeExecutor | None = None,
) -> object:
    """Execute a bridge call via subprocess (or injected executor for tests).

    - Exit 0 + valid JSON → deserialize() the value
    - Exit 0 + invalid JSON → LumonError
    - Non-zero exit → LumonTag("error", stderr[:1024].strip())
    - Executable not found → LumonError
    """
    if executor is not None:
        return executor(name, args, run_cmd, working_dir)

    payload = json.dumps({"function": name, "args": args})

    try:
        result = subprocess.run(
            shlex.split(run_cmd),
            input=payload,
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=30,
        )
    except FileNotFoundError:
        raise LumonError(f"Bridge executable not found: {run_cmd}")
    except subprocess.TimeoutExpired:
        raise LumonError(f"Bridge '{name}' timed out after 30 seconds")

    if result.returncode != 0:
        stderr_msg = result.stderr[:1024].strip() if result.stderr else "unknown error"
        return LumonTag("error", stderr_msg)

    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        raise LumonError(
            f"Bridge '{name}' returned invalid JSON on exit 0",
            function=name,
        )

    return deserialize(parsed)
