"""Top-level entry point for the Lumon interpreter."""

from __future__ import annotations

import os

from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal, SpawnSignal
from lumon.evaluator import eval_node
from lumon.parser import parse
from lumon.serializer import serialize
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


def interpret(
    code: str,
    *,
    io_backend: object = None,
    http_backend: object = None,
    responses: list[object] | None = None,
    working_dir: str | None = None,
    persist: bool = False,
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
            _setup_loader(env, working_dir)
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
    from lumon.source_utils import extract_blocks, save_blocks

    blocks = extract_blocks(code)
    if blocks:
        save_blocks(working_dir, blocks)
