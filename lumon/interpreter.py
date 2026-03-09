"""Top-level entry point for the Lumon interpreter."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import uuid
from collections.abc import Callable

from lumon.builtins import register_builtins
from lumon.daemon import SuspendEvent
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal
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

_PLUGIN_RESERVED_KEYS = {"plugin", "env", "expose"}


def _setup_loader(env: Environment, working_dir: str) -> None:
    """Set up a lazy loader that reads manifest+impl files from disk."""

    def loader(namespace: str) -> None:
        manifest_path = os.path.join(working_dir, "lumon", "manifests", f"{namespace}.lumon")
        impl_path = os.path.join(working_dir, "lumon", "impl", f"{namespace}.lumon")

        for path in (manifest_path, impl_path):
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    source = f.read()
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
            with open(plugin.manifest_path, encoding="utf-8") as f:
                source = f.read()
            try:
                ast = parse(source)
                eval_node(ast, env)
            except LumonError:
                raise
            except Exception as e:
                raise LumonError(f"Error loading plugin manifest {plugin.manifest_path}: {e}") from e

        # Parse and register impl (implements)
        if os.path.isfile(plugin.impl_path):
            with open(plugin.impl_path, encoding="utf-8") as f:
                source = f.read()
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
                    env._defines[alias_name] = dataclasses.replace(  # type: ignore[type-var]
                        old_node, namespace_path=alias_name
                    )
            for fn_name in list(env._implements.keys()):
                if fn_name.startswith(source_prefix):
                    alias_name = plugin.alias + "." + fn_name.split(".", 1)[1]
                    old_node = env._implements.pop(fn_name)
                    env._implements[alias_name] = dataclasses.replace(  # type: ignore[type-var]
                        old_node, namespace_path=alias_name
                    )
            # Register the alias as a namespace prefix
            env._namespace_prefixes.add(plugin.alias)

        # Get instance config and strip reserved keys
        instance_config = plugin_config.get(plugin.alias, {})
        if not isinstance(instance_config, dict):
            instance_config = {}

        # Filter by expose list if present
        if "expose" in instance_config:
            expose_list = instance_config["expose"]
            if not isinstance(expose_list, list):
                raise LumonError(f"'expose' for plugin '{plugin.alias}' must be a list")
            allowed_fns = {plugin.alias + "." + name for name in expose_list}
            for fn_name in list(env._defines.keys()):
                if fn_name.startswith(plugin.alias + ".") and fn_name not in allowed_fns:
                    env._defines.pop(fn_name)
                    env._implements.pop(fn_name, None)

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
    git_backend: object = None,
    responses: list[object] | None = None,
    working_dir: str | None = None,
    persist: bool = False,
    plugin_executor: Callable[..., object] | None = None,
    comm_dir: str | None = None,
) -> dict:
    """Parse, type-check, and execute Lumon code.

    Returns a dict matching the output protocol:
      {"type": "result", "value": ...}
      {"type": "error", "function": ..., "trace": [...], "inputs": {...}, "message": ...}
      {"type": "ask", "prompt": ..., "context": ..., "expects": ...}
      {"type": "spawn_batch", ...}

    When *comm_dir* is set, large context data for ask/spawn is written to
    files under that directory instead of being inlined in the output JSON.
    """
    env = Environment()
    try:
        ast = parse(code)
        type_check(ast, io_backend=io_backend, git_backend=git_backend)
        if responses:
            env._response_queue.extend(responses)
        register_builtins(env, io_backend, git_backend)
        if working_dir is not None:
            env._working_dir = working_dir
            _setup_loader(env, working_dir)
            _setup_plugins(env, working_dir, plugin_executor)
        elif plugin_executor is not None:
            env._plugin_executor = plugin_executor
        result = eval_node(ast, env)
        pending = env.get_pending_spawns()
        if pending:
            return _make_spawn_batch(pending, env._logs, comm_dir=comm_dir)
        output: dict[str, object] = {"type": "result", "value": serialize(result)}
        if env._logs:
            output["logs"] = list(env._logs)
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except ReturnSignal as rs:
        pending = env.get_pending_spawns()
        if pending:
            return _make_spawn_batch(pending, env._logs, comm_dir=comm_dir)
        output = {"type": "result", "value": serialize(rs.value)}
        if env._logs:
            output["logs"] = list(env._logs)
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except AskSignal as ask:
        envelope = ask.envelope
        if env._logs:
            envelope["logs"] = list(env._logs)
        if comm_dir is not None:
            envelope = _externalize_ask(envelope, comm_dir)
        return envelope
    except LumonError as e:
        envelope = e.to_envelope()
        if env._logs:
            envelope["logs"] = list(env._logs)
        return envelope
    except RecursionError:
        envelope = LumonError("Call depth limit exceeded").to_envelope()
        if env._logs:
            envelope["logs"] = list(env._logs)
        return envelope


def _make_spawn_batch(
    pending: list[tuple[str, dict]],
    logs: list[object] | None = None,
    *,
    comm_dir: str | None = None,
) -> dict:
    """Build a spawn_batch envelope from pending spawn requests."""
    spawns = [envelope for _handle, envelope in pending]
    if comm_dir is not None:
        spawns = _externalize_spawns(spawns, comm_dir)
    if len(spawns) == 1:
        result = {"type": "spawn_batch", **spawns[0]}
    else:
        result = {"type": "spawn_batch", "spawns": spawns}
    if comm_dir is not None:
        result["session"] = os.path.basename(comm_dir)
    if logs:
        result["logs"] = list(logs)
    return result


def generate_session_id() -> str:
    """Generate an 8-character hex session ID."""
    return uuid.uuid4().hex[:8]


def _write_comm_file(path: str, data: object) -> None:
    """Write JSON data to a comm file, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _externalize_spawns(spawns: list[dict], comm_dir: str) -> list[dict]:
    """Write spawn context to files and return lightweight envelopes."""
    result: list[dict] = []
    for i, spawn in enumerate(spawns):
        spawn_id = f"spawn_{i}"
        lightweight: dict[str, object] = {"spawn_id": spawn_id}

        # Copy prompt (always inline)
        if "prompt" in spawn:
            prompt = str(spawn["prompt"])
            # Write context to file if present, append path to prompt
            if "context" in spawn:
                context_file = os.path.join(comm_dir, f"{spawn_id}_context.json")
                _write_comm_file(context_file, spawn["context"])
                prompt += f"\n\nContext data: {context_file}"
                lightweight["context_file"] = context_file
            lightweight["prompt"] = prompt

        # Copy expects inline (small)
        if "expects" in spawn:
            lightweight["expects"] = spawn["expects"]

        # Copy fork inline (small)
        if "fork" in spawn:
            lightweight["fork"] = spawn["fork"]

        # Add response file path
        response_file = os.path.join(comm_dir, f"{spawn_id}_response.json")
        lightweight["response_file"] = response_file

        result.append(lightweight)
    return result


def _externalize_ask(envelope: dict, comm_dir: str) -> dict:
    """Write ask context to a file and return a lightweight envelope."""
    lightweight: dict[str, object] = {"type": "ask"}
    lightweight["session"] = os.path.basename(comm_dir)

    prompt = str(envelope.get("prompt", ""))
    if "context" in envelope:
        context_file = os.path.join(comm_dir, "ask_context.json")
        _write_comm_file(context_file, envelope["context"])
        prompt += f"\n\nContext data: {context_file}"
        lightweight["context_file"] = context_file
    lightweight["prompt"] = prompt

    if "expects" in envelope:
        lightweight["expects"] = envelope["expects"]

    response_file = os.path.join(comm_dir, "ask_response.json")
    lightweight["response_file"] = response_file

    if "logs" in envelope:
        lightweight["logs"] = envelope["logs"]

    return lightweight


def _persist_blocks(code: str, working_dir: str) -> None:
    """Extract define/implement blocks from code and save to disk."""
    blocks = extract_blocks(code)
    if blocks:
        save_blocks(working_dir, blocks)


def cleanup_comm_dir(comm_dir: str) -> None:
    """Remove a session's comm directory. Also removes parent if empty."""
    if os.path.isdir(comm_dir):
        shutil.rmtree(comm_dir)
    # Remove parent .lumon_comm if now empty
    parent = os.path.dirname(comm_dir)
    if parent and os.path.isdir(parent):
        try:
            os.rmdir(parent)  # Only removes if empty
        except OSError:
            pass


def cleanup_all_comm(base_dir: str = ".lumon_comm") -> None:
    """Remove the entire .lumon_comm directory (stale sessions)."""
    if os.path.isdir(base_dir):
        shutil.rmtree(base_dir)


def interpret_with_suspend(
    code: str,
    *,
    io_backend: object = None,
    git_backend: object = None,
    working_dir: str | None = None,
    persist: bool = False,
    comm_dir: str | None = None,
    suspend_event: object | None = None,
) -> dict:
    """Like interpret(), but uses a SuspendEvent for daemon mode.

    When suspend_event is set, ask expressions block on the event instead of
    raising AskSignal. Spawn batches also block for responses.
    """
    env = Environment()
    if isinstance(suspend_event, SuspendEvent):
        env._suspend_callback = suspend_event

    try:
        ast = parse(code)
        type_check(ast, io_backend=io_backend, git_backend=git_backend)
        register_builtins(env, io_backend, git_backend)
        if working_dir is not None:
            env._working_dir = working_dir
            _setup_loader(env, working_dir)
            _setup_plugins(env, working_dir)
        result = eval_node(ast, env)
        pending = env.get_pending_spawns()
        if pending:
            batch_envelope = _make_spawn_batch(pending, env._logs, comm_dir=comm_dir)
            if isinstance(suspend_event, SuspendEvent):
                # Block for spawn responses
                responses = suspend_event.suspend_for_spawns(batch_envelope)
                # Feed responses back and continue (spawns are terminal in current model)
                # In current Lumon, spawns collect handles and return at program end,
                # so we just pair responses with handles
                handle_map: dict[str, object] = {}
                for i, (handle, _envelope) in enumerate(pending):
                    if i < len(responses):
                        handle_map[handle] = responses[i]
                # Re-run with responses queued? No — spawns are collected at end.
                # The result is the list of spawn responses.
                output: dict[str, object] = {"type": "result", "value": serialize(list(responses))}
                if env._logs:
                    output["logs"] = list(env._logs)
                if persist and working_dir is not None:
                    _persist_blocks(code, working_dir)
                return output
            return batch_envelope
        output = {"type": "result", "value": serialize(result)}
        if env._logs:
            output["logs"] = list(env._logs)
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except ReturnSignal as rs:
        pending = env.get_pending_spawns()
        if pending:
            batch_envelope = _make_spawn_batch(pending, env._logs, comm_dir=comm_dir)
            if isinstance(suspend_event, SuspendEvent):
                responses = suspend_event.suspend_for_spawns(batch_envelope)
                output = {"type": "result", "value": serialize(list(responses))}
                if env._logs:
                    output["logs"] = list(env._logs)
                if persist and working_dir is not None:
                    _persist_blocks(code, working_dir)
                return output
            return batch_envelope
        output = {"type": "result", "value": serialize(rs.value)}
        if env._logs:
            output["logs"] = list(env._logs)
        if persist and working_dir is not None:
            _persist_blocks(code, working_dir)
        return output
    except AskSignal as ask:
        # Should not happen in daemon mode (asks block instead of raising)
        envelope = ask.envelope
        if env._logs:
            envelope["logs"] = list(env._logs)
        if comm_dir is not None:
            envelope = _externalize_ask(envelope, comm_dir)
        return envelope
    except LumonError as e:
        envelope = e.to_envelope()
        if env._logs:
            envelope["logs"] = list(env._logs)
        return envelope
    except RecursionError:
        envelope = LumonError("Call depth limit exceeded").to_envelope()
        if env._logs:
            envelope["logs"] = list(env._logs)
        return envelope
