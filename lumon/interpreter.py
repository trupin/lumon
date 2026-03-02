"""Top-level entry point for the Lumon interpreter."""

from __future__ import annotations

from lumon.builtins import register_builtins
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal, SpawnSignal
from lumon.evaluator import eval_node
from lumon.parser import parse
from lumon.serializer import serialize
from lumon.type_checker import type_check


def interpret(code: str, *, io_backend: object = None, http_backend: object = None) -> dict:
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
        register_builtins(env, io_backend, http_backend)
        result = eval_node(ast, env)
        return {"type": "result", "value": serialize(result)}
    except ReturnSignal as rs:
        return {"type": "result", "value": serialize(rs.value)}
    except AskSignal as ask:
        return ask.envelope
    except SpawnSignal as spawn:
        return spawn.envelope
    except LumonError as e:
        return e.to_envelope()
    except RecursionError:
        return LumonError("Call depth limit exceeded").to_envelope()
