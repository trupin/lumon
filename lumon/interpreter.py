"""Top-level entry point for the Lumon interpreter."""

from __future__ import annotations

import os
from collections.abc import Callable

from lumon.bridge import load_bridges
from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal, SpawnSignal
from lumon.evaluator import eval_node
from lumon.parser import parse
from lumon.serializer import serialize
from lumon.source_utils import extract_blocks, save_blocks
from lumon.type_checker import type_check


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


def _setup_bridges(env: Environment, working_dir: str, bridge_executor: Callable[..., object] | None = None) -> None:
    """Load bridge declarations and register them in the environment."""
    bridges = load_bridges(working_dir)
    if not bridges:
        return

    if bridge_executor is not None:
        env._bridge_executor = bridge_executor

    for name, run_cmd in bridges.items():
        # Trigger the lazy loader for this namespace so the define gets loaded
        ns = name.split(".")[0]
        env.trigger_loader(ns)

        # Validate: every bridge must have a corresponding define
        if name not in env._defines:
            raise LumonError(
                f"Bridge '{name}' has no matching define in manifests"
            )

        env.register_bridge(name, run_cmd)


def interpret(
    code: str,
    *,
    io_backend: object = None,
    http_backend: object = None,
    responses: list[object] | None = None,
    working_dir: str | None = None,
    persist: bool = False,
    bridge_executor: Callable[..., object] | None = None,
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
        type_check(ast, io_backend=io_backend, http_backend=http_backend)
        env = Environment()
        if responses:
            env._response_queue.extend(responses)
        register_builtins(env, io_backend, http_backend)
        if working_dir is not None:
            env._working_dir = working_dir
            _setup_loader(env, working_dir)
            _setup_bridges(env, working_dir, bridge_executor)
        elif bridge_executor is not None:
            env._bridge_executor = bridge_executor
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
