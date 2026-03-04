"""Top-level entry point for the Lumon interpreter."""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Callable

from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal, SpawnSignal
from lumon.evaluator import eval_node
from lumon.parser import parse
from lumon.plugins import (
    discover_plugins,
    disk_manifest_namespaces,
    load_config,
    split_contracts,
)
from lumon.serializer import serialize
from lumon.source_utils import extract_blocks, save_blocks
from lumon.type_checker import type_check

_PLUGIN_RESERVED_KEYS = {"plugin", "env"}


def _setup_loader(env: Environment, working_dir: str) -> None:
    """Set up a lazy loader that reads manifest+impl files from disk."""

    def loader(namespace: str) -> None:
        manifest_path = os.path.join(working_dir, "lumon", "manifests", f"{namespace}.lumon")
        impl_path = os.path.join(working_dir, "lumon", "impl", f"{namespace}.lumon")

        for path in (manifest_path, impl_path):
            if os.path.isfile(path):
                source = open(path, encoding="utf-8").read()
                try:
                    ast = parse(source)
                    eval_node(ast, env)
                except LumonError:
                    raise
                except Exception as e:
                    raise LumonError(f"Error loading {path}: {e}") from e

    env.set_loader(loader)


def _setup_plugins(
    env: Environment,
    working_dir: str,
    plugin_executor: Callable[..., object] | None = None,
) -> None:
    """Discover and register plugins from ../plugins/ based on .lumon.json."""
    config = load_config(working_dir)
    plugins = discover_plugins(working_dir, config)
    if not plugins:
        return

    # Detect namespace conflicts between plugins and disk manifests
    disk_namespaces = disk_manifest_namespaces(working_dir)
    for plugin in plugins:
        if plugin.alias in disk_namespaces:
            raise LumonError(
                f"Namespace conflict: '{plugin.alias}' is both a plugin alias "
                f"and a disk manifest (lumon/manifests/{plugin.alias}.lumon). "
                f"Remove one to avoid ambiguity."
            )

    if plugin_executor is not None:
        env._plugin_executor = plugin_executor

    plugin_config = config.get("plugins", {})

    for plugin in plugins:
        # Parse and register manifest (defines)
        if os.path.isfile(plugin.manifest_path):
            source = open(plugin.manifest_path, encoding="utf-8").read()
            try:
                ast = parse(source)
                eval_node(ast, env)
            except LumonError:
                raise
            except Exception as e:
                raise LumonError(f"Error loading plugin manifest {plugin.manifest_path}: {e}") from e

        # Parse and register impl (implements)
        if os.path.isfile(plugin.impl_path):
            source = open(plugin.impl_path, encoding="utf-8").read()
            try:
                ast = parse(source)
                eval_node(ast, env)
            except LumonError:
                raise
            except Exception as e:
                raise LumonError(f"Error loading plugin impl {plugin.impl_path}: {e}") from e

        # Rename defines/implements from source prefix to alias prefix (when they differ)
        if plugin.alias != plugin.name:
            source_prefix = plugin.name + "."
            for fn_name in list(env._defines.keys()):
                if fn_name.startswith(source_prefix):
                    alias_name = plugin.alias + "." + fn_name.split(".", 1)[1]
                    old_node = env._defines.pop(fn_name)
                    env._defines[alias_name] = dataclasses.replace(old_node, namespace_path=alias_name)  # type: ignore[type-var]
            for fn_name in list(env._implements.keys()):
                if fn_name.startswith(source_prefix):
                    alias_name = plugin.alias + "." + fn_name.split(".", 1)[1]
                    old_node = env._implements.pop(fn_name)
                    env._implements[alias_name] = dataclasses.replace(old_node, namespace_path=alias_name)  # type: ignore[type-var]
            # Register the alias as a namespace prefix
            env._namespace_prefixes.add(plugin.alias)

        # Get instance config and strip reserved keys
        instance_config = plugin_config.get(plugin.alias, {})
        if not isinstance(instance_config, dict):
            instance_config = {}

        # Extract env vars from "env" key
        custom_env: dict[str, str] = {}
        if "env" in instance_config:
            raw_env = instance_config["env"]
            if isinstance(raw_env, dict):
                custom_env = {str(k): str(v) for k, v in raw_env.items()}

        # Build function-level contracts (strip reserved keys)
        fn_contracts = {k: v for k, v in instance_config.items() if k not in _PLUGIN_RESERVED_KEYS}

        # Record plugin dirs, contracts, forced values, and env vars
        for fn_name in list(env._defines.keys()):
            if fn_name.startswith(plugin.alias + "."):
                env._plugin_dirs[fn_name] = plugin.path
                short_name = fn_name.split(".", 1)[1]

                # Store instance identity and env vars for each function
                env._plugin_instances[fn_name] = plugin.alias
                if custom_env:
                    env._plugin_env_vars[fn_name] = custom_env

                if isinstance(fn_contracts, dict) and short_name in fn_contracts:
                    param_contracts = fn_contracts[short_name]
                    if isinstance(param_contracts, dict):
                        dynamic, forced = split_contracts(param_contracts)
                        if dynamic:
                            env._plugin_contracts[fn_name] = dynamic
                        if forced:
                            env._plugin_forced_values[fn_name] = forced

        # Trigger lazy loader so user impls in sandbox/lumon/impl/ can override
        env.trigger_loader(plugin.alias)


def interpret(
    code: str,
    *,
    io_backend: object = None,
    http_backend: object = None,
    git_backend: object = None,
    responses: list[object] | None = None,
    working_dir: str | None = None,
    persist: bool = False,
    plugin_executor: Callable[..., object] | None = None,
) -> dict:
    """Parse, type-check, and execute Lumon code.

    Returns a dict matching the output protocol:
      {"type": "result", "value": ...}
      {"type": "error", "function": ..., "trace": [...], "inputs": {...}, "message": ...}
      {"type": "ask", "prompt": ..., "context": ..., "expects": ...}
      {"type": "spawn_batch", ...}
    """
    try:
        ast = parse(code)
        type_check(ast, io_backend=io_backend, http_backend=http_backend, git_backend=git_backend)
        env = Environment()
        if responses:
            env._response_queue.extend(responses)
        register_builtins(env, io_backend, http_backend, git_backend)
        if working_dir is not None:
            env._working_dir = working_dir
            _setup_loader(env, working_dir)
            _setup_plugins(env, working_dir, plugin_executor)
        elif plugin_executor is not None:
            env._plugin_executor = plugin_executor
        result = eval_node(ast, env)
        output = {"type": "result", "value": serialize(result)}
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except ReturnSignal as rs:
        output = {"type": "result", "value": serialize(rs.value)}
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except AskSignal as ask:
        return ask.envelope
    except SpawnSignal as spawn:
        return spawn.envelope
    except LumonError as e:
        return e.to_envelope()
    except RecursionError:
        return LumonError("Call depth limit exceeded").to_envelope()


def _persist_blocks(code: str, working_dir: str) -> None:
    """Extract define/implement blocks from code and save to disk."""
    blocks = extract_blocks(code)
    if blocks:
        save_blocks(working_dir, blocks)
