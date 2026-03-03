"""Plugin system: self-contained plugin directories with contracts."""

from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from lumon.ast_nodes import DefineBlock, ParamDef
from lumon.errors import LumonError
from lumon.serializer import deserialize
from lumon.values import LumonTag


@dataclass
class PluginInfo:
    """Metadata for a discovered plugin directory."""

    name: str
    path: str
    manifest_path: str
    impl_path: str


def load_config(working_dir: str) -> dict:
    """Read .lumon.json from the parent of working_dir.

    Returns parsed JSON or {} if file doesn't exist.
    Raises LumonError on invalid JSON.
    """
    config_path = os.path.join(working_dir, "..", ".lumon.json")
    config_path = os.path.normpath(config_path)
    if not os.path.isfile(config_path):
        return {}
    with open(config_path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            raise LumonError(f"Invalid .lumon.json: {e}") from e


def discover_plugins(working_dir: str, config: dict) -> list[PluginInfo]:
    """Scan ../plugins/ for subdirectories listed in config["plugins"].

    Each subdir with a manifest.lumon is a plugin.
    Returns list of PluginInfo for allowed plugins only.
    """
    allowed = config.get("plugins", {})
    if not allowed:
        return []

    plugins_dir = os.path.normpath(os.path.join(working_dir, "..", "plugins"))
    if not os.path.isdir(plugins_dir):
        return []

    result: list[PluginInfo] = []
    for name in sorted(os.listdir(plugins_dir)):
        if name not in allowed:
            continue
        plugin_path = os.path.join(plugins_dir, name)
        if not os.path.isdir(plugin_path):
            continue
        manifest_path = os.path.join(plugin_path, "manifest.lumon")
        impl_path = os.path.join(plugin_path, "impl.lumon")
        if not os.path.isfile(manifest_path):
            continue
        result.append(PluginInfo(
            name=name,
            path=plugin_path,
            manifest_path=manifest_path,
            impl_path=impl_path,
        ))
    return result


def validate_contracts(
    name: str, args: tuple[object, ...], define: DefineBlock, contracts: dict
) -> None:
    """Validate arguments against parameter contracts.

    Contract types:
    - Text wildcard: "pattern*" — fnmatch against text args
    - Number range: [min, max] — inclusive range for number args
    - Enum: ["a", "b"] (list of strings) — allowed values for text args
    """
    if not define.params:
        return

    for i, param in enumerate(define.params):
        assert isinstance(param, ParamDef)
        if param.name not in contracts:
            continue
        if i >= len(args):
            continue

        contract = contracts[param.name]
        value = args[i]

        if isinstance(contract, str):
            # Text wildcard
            if not isinstance(value, str):
                raise LumonError(
                    f"Contract violation in {name}: parameter '{param.name}' "
                    f"expected text, got {type(value).__name__}"
                )
            if not fnmatch.fnmatch(value, contract):
                raise LumonError(
                    f"Contract violation in {name}: parameter '{param.name}' "
                    f'value "{value}" does not match pattern "{contract}"'
                )

        elif isinstance(contract, list):
            if len(contract) == 2 and all(isinstance(v, (int, float)) for v in contract):
                # Number range [min, max]
                if not isinstance(value, (int, float)):
                    raise LumonError(
                        f"Contract violation in {name}: parameter '{param.name}' "
                        f"expected number, got {type(value).__name__}"
                    )
                lo, hi = contract
                if not (lo <= value <= hi):
                    raise LumonError(
                        f"Contract violation in {name}: parameter '{param.name}' "
                        f"value {value} outside range [{lo}, {hi}]"
                    )
            elif all(isinstance(v, str) for v in contract):
                # Enum (list of strings)
                if not isinstance(value, str):
                    raise LumonError(
                        f"Contract violation in {name}: parameter '{param.name}' "
                        f"expected text, got {type(value).__name__}"
                    )
                if value not in contract:
                    raise LumonError(
                        f"Contract violation in {name}: parameter '{param.name}' "
                        f'value "{value}" not in allowed values {contract}'
                    )


PluginExecutor = Callable[[str, dict[str, object], str], object]
"""Signature: (command, args_dict, plugin_dir) -> result value."""


def exec_plugin_script(
    plugin_dir: str,
    command: str,
    args: object = None,
    executor: PluginExecutor | None = None,
) -> object:
    """Execute a plugin script via subprocess (or injected executor for tests).

    - Exit 0 + valid JSON → deserialize() the value
    - Exit 0 + invalid JSON → LumonError
    - Non-zero exit → LumonTag("error", stderr[:1024].strip())
    - Executable not found → LumonError
    - Timeout (30s) → LumonError
    """
    args_map = args if isinstance(args, dict) else {}

    if executor is not None:
        return executor(command, args_map, plugin_dir)

    payload = json.dumps(args_map)

    try:
        result = subprocess.run(
            shlex.split(command),
            input=payload,
            capture_output=True,
            text=True,
            cwd=plugin_dir,
            timeout=30,
        )
    except FileNotFoundError:
        raise LumonError(f"Plugin executable not found: {command}")
    except subprocess.TimeoutExpired:
        raise LumonError(f"Plugin script timed out after 30 seconds: {command}")

    if result.returncode != 0:
        stderr_msg = result.stderr[:1024].strip() if result.stderr else "unknown error"
        return LumonTag("error", stderr_msg)

    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        raise LumonError(
            f"Plugin script returned invalid JSON on exit 0: {command}",
        )

    return deserialize(parsed)
