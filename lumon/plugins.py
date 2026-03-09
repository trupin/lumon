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
    alias: str
    path: str
    manifest_path: str
    impl_path: str


def classify_contract(value: object) -> str:
    """Classify a contract value as 'dynamic' or 'forced'.

    Dynamic (agent provides, system validates):
      - string containing '*' (wildcard)
      - [min, max] number range
      - ["a", "b"] string enum
    Forced (system injects, agent never sees):
      - plain string (no '*')
      - plain number
      - plain boolean
    """
    if isinstance(value, bool):
        return "forced"
    if isinstance(value, str):
        return "dynamic" if "*" in value else "forced"
    if isinstance(value, (int, float)):
        return "forced"
    if isinstance(value, list) and len(value) > 0:
        if len(value) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "dynamic"  # number range
        if all(isinstance(v, str) for v in value):
            return "dynamic"  # enum
    return "forced"


def split_contracts(contracts: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    """Split a contract dict into (dynamic, forced) dicts."""
    dynamic: dict[str, object] = {}
    forced: dict[str, object] = {}
    for key, value in contracts.items():
        if classify_contract(value) == "dynamic":
            dynamic[key] = value
        else:
            forced[key] = value
    return dynamic, forced


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


def disk_manifest_namespaces(working_dir: str) -> set[str]:
    """Return the set of namespace names that have disk manifests.

    Scans ``<working_dir>/lumon/manifests/*.lumon`` and returns the
    stem of each file (e.g. ``{"inbox", "math"}``).
    """
    manifest_dir = os.path.join(working_dir, "lumon", "manifests")
    if not os.path.isdir(manifest_dir):
        return set()
    return {
        fname[:-6]
        for fname in os.listdir(manifest_dir)
        if fname.endswith(".lumon")
    }


def discover_plugins(working_dir: str, config: dict) -> list[PluginInfo]:
    """Scan ../plugins/ for subdirectories listed in config["plugins"].

    Each subdir with a manifest.lumon is a plugin.
    Supports multi-instance: config key is the alias, optional "plugin" key
    points to the source directory. If absent, alias == source dir name.
    Returns list of PluginInfo for allowed plugins only.
    """
    allowed = config.get("plugins", {})
    if not allowed:
        return []

    plugins_dir = os.path.normpath(os.path.join(working_dir, "..", "plugins"))
    if not os.path.isdir(plugins_dir):
        return []

    result: list[PluginInfo] = []
    for alias in sorted(allowed.keys()):
        instance_config = allowed[alias]
        # Resolve source directory: "plugin" key or alias itself
        source_name = alias
        if isinstance(instance_config, dict) and "plugin" in instance_config:
            source_name = instance_config["plugin"]
        plugin_path = os.path.join(plugins_dir, source_name)
        if not os.path.isdir(plugin_path):
            continue
        manifest_path = os.path.join(plugin_path, "manifest.lumon")
        impl_path = os.path.join(plugin_path, "impl.lumon")
        if not os.path.isfile(manifest_path):
            continue
        result.append(PluginInfo(
            name=source_name,
            alias=alias,
            path=plugin_path,
            manifest_path=manifest_path,
            impl_path=impl_path,
        ))
    return result


def _normalize_url(value: str) -> str:
    """Append trailing slash to bare HTTP(S) domain URLs.

    Browsers treat ``https://example.com`` and ``https://example.com/``
    identically.  Normalising before ``fnmatch`` ensures that a wildcard
    contract like ``https://example.com/*`` matches both forms.
    """
    if not (value.startswith("http://") or value.startswith("https://")):
        return value
    after_scheme = value.split("//", 1)
    if len(after_scheme) < 2:
        return value
    rest = after_scheme[1]
    # Strip query and fragment before checking for a path separator
    host_part = rest.split("?", 1)[0].split("#", 1)[0]
    if "/" not in host_part:
        # Insert slash before query/fragment, or append at end
        insert_pos = len(value)
        for delim in ("?", "#"):
            idx = rest.find(delim)
            if idx != -1:
                insert_pos = len(after_scheme[0]) + 2 + idx
                break
        return value[:insert_pos] + "/" + value[insert_pos:]
    return value


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
            normalized = _normalize_url(value)
            if not fnmatch.fnmatch(normalized, contract):
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
                if value < lo or value > hi:
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


PluginExecutor = Callable[[str, dict[str, object], str, str], object]
"""Signature: (command, args_dict, plugin_dir, instance) -> result value."""


def exec_plugin_script(
    plugin_dir: str,
    command: str,
    args: object = None,
    executor: PluginExecutor | None = None,
    instance: str = "",
    env_vars: dict[str, str] | None = None,
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
        return executor(command, args_map, plugin_dir, instance)

    payload = json.dumps(args_map)

    # Build subprocess environment with instance identity and custom env vars
    sub_env = {**os.environ, "LUMON_PLUGIN_INSTANCE": instance}
    if env_vars:
        sub_env.update(env_vars)

    try:
        result = subprocess.run(
            shlex.split(command),
            input=payload,
            capture_output=True,
            text=True,
            cwd=plugin_dir,
            timeout=300,
            env=sub_env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LumonError(f"Plugin executable not found: {command}") from exc
    except subprocess.TimeoutExpired as exc:
        raise LumonError(f"Plugin script timed out after 30 seconds: {command}") from exc

    if result.returncode != 0:
        stderr_msg = result.stderr[:1024].strip() if result.stderr else "unknown error"
        return LumonTag("error", stderr_msg)

    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LumonError(
            f"Plugin script returned invalid JSON on exit 0: {command}",
        ) from exc

    return deserialize(parsed)
