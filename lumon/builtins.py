"""Built-in function implementations for all Lumon namespaces."""

from __future__ import annotations

import math

from lumon.environment import Environment
from lumon.errors import LumonError
from lumon.plugins import exec_plugin_script
from lumon.values import LumonFunction, LumonTag, is_truthy


def _call_fn(fn_val: object, args: list[object]) -> object:
    """Call a LumonFunction or Python callable with args."""
    if isinstance(fn_val, LumonFunction):
        from lumon.evaluator import call_lumon_fn  # circular: evaluator imports builtins
        return call_lumon_fn(fn_val, args)
    if callable(fn_val):
        return fn_val(*args)
    raise TypeError(f"Not callable: {type(fn_val)}")


def _type_of(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, LumonTag):
        return "tag"
    return "unknown"


def _type_is(value: object, type_name: str) -> bool:
    return _type_of(value) == type_name


def _text_from(value: object) -> str:
    if value is None:
        return "none"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        inner = ", ".join(_text_from(item) for item in value)
        return f"[{inner}]"
    if isinstance(value, dict):
        entries = ", ".join(f"{k}: {_text_from(v)}" for k, v in value.items())
        return "{" + entries + "}"
    if isinstance(value, LumonTag):
        if value.payload is None:
            return f":{value.name}"
        return f":{value.name}({_text_from(value.payload)})"
    return str(value)


def _number_parse(s: str) -> object:
    try:
        if "." in s:
            return float(s)
        return int(s)
    except (ValueError, TypeError):
        return None


def _list_fold(items: list, init: object, f: object) -> object:
    acc = init
    for item in items:
        acc = _call_fn(f, [acc, item])
    return acc


def _list_flat_map(items: list, f: object) -> list:
    result: list = []
    for item in items:
        sub = _call_fn(f, [item])
        if isinstance(sub, list):
            result.extend(sub)
        else:
            result.append(sub)
    return result


def _list_deduplicate(items: list) -> list:
    seen: list = []
    result: list = []
    for item in items:
        # Simple equality check
        found = False
        for s in seen:
            if item == s:
                found = True
                break
        if not found:
            seen.append(item)
            result.append(item)
    return result


def _wrap_tag_result(backend_result: dict) -> LumonTag:
    """Convert a MockFS/MockHTTP dict result to a LumonTag."""
    tag_name = backend_result.get("tag", "error")
    payload = backend_result.get("value")
    return LumonTag(tag_name, payload)


def _is_truthy_for_filter(value: object) -> bool:
    return is_truthy(value)


def register_builtins(
    env: Environment,
    io_backend: object | None = None,
    http_backend: object | None = None,
) -> None:
    """Register all built-in functions in the environment."""

    # --- text.* ---
    env.register_builtin("text.split", lambda s, sep: s.split(sep))
    env.register_builtin("text.join", lambda items, sep: sep.join(items))
    env.register_builtin("text.contains", lambda s, sub: sub in s)
    env.register_builtin("text.replace", lambda s, old, new: s.replace(old, new))
    env.register_builtin(
        "text.slice",
        lambda s, start, end: s[max(0, int(start)) : min(len(s), int(end))],
    )
    env.register_builtin("text.length", lambda s: len(s))
    env.register_builtin("text.upper", lambda s: s.upper())
    env.register_builtin("text.lower", lambda s: s.lower())
    env.register_builtin("text.trim", lambda s: s.strip())
    env.register_builtin("text.starts_with", lambda s, prefix: s.startswith(prefix))
    env.register_builtin("text.ends_with", lambda s, suffix: s.endswith(suffix))
    env.register_builtin("text.from", _text_from)

    # --- list.* ---
    env.register_builtin(
        "list.map", lambda items, f: [_call_fn(f, [item]) for item in items]
    )
    env.register_builtin(
        "list.filter",
        lambda items, f: [
            item for item in items if _is_truthy_for_filter(_call_fn(f, [item]))
        ],
    )
    env.register_builtin("list.fold", _list_fold)
    env.register_builtin("list.flat_map", _list_flat_map)
    env.register_builtin("list.sort", lambda items: sorted(items))
    env.register_builtin(
        "list.sort_by",
        lambda items, f: sorted(items, key=lambda x: _call_fn(f, [x])),  # type: ignore[type-var]
    )
    env.register_builtin("list.take", lambda items, n: items[: int(n)])
    env.register_builtin("list.drop", lambda items, n: items[int(n) :])
    env.register_builtin("list.deduplicate", _list_deduplicate)
    env.register_builtin("list.length", lambda items: len(items))
    env.register_builtin("list.contains", lambda items, item: item in items)
    env.register_builtin("list.reverse", lambda items: list(reversed(items)))
    env.register_builtin(
        "list.flatten", lambda items: [x for sub in items for x in sub]
    )
    env.register_builtin("list.head", lambda items: items[0] if items else None)
    env.register_builtin("list.tail", lambda items: items[1:] if items else [])
    env.register_builtin("list.concat", lambda a, b: a + b)

    # --- map.* ---
    env.register_builtin("map.get", lambda m, key: m.get(key))
    env.register_builtin("map.set", lambda m, key, val: {**m, key: val})
    env.register_builtin("map.keys", lambda m: list(m.keys()))
    env.register_builtin("map.values", lambda m: list(m.values()))
    env.register_builtin("map.merge", lambda a, b: {**a, **b})
    env.register_builtin("map.has", lambda m, key: key in m)
    env.register_builtin(
        "map.remove", lambda m, key: {k: v for k, v in m.items() if k != key}
    )
    env.register_builtin(
        "map.entries",
        lambda m: [{"key": k, "value": v} for k, v in m.items()],
    )

    # --- number.* ---
    env.register_builtin("number.round", lambda n: round(n))
    env.register_builtin("number.floor", lambda n: math.floor(n))
    env.register_builtin("number.ceil", lambda n: math.ceil(n))
    env.register_builtin("number.abs", lambda n: abs(n))
    env.register_builtin("number.min", lambda a, b: min(a, b))
    env.register_builtin("number.max", lambda a, b: max(a, b))
    env.register_builtin("number.parse", _number_parse)

    # --- type.* ---
    env.register_builtin("type.of", _type_of)
    env.register_builtin("type.is", _type_is)

    # --- io.* ---
    if io_backend is not None:
        _io = io_backend
        env.register_builtin(
            "io.read", lambda path: _wrap_tag_result(_io.read(path))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.write",
            lambda path, content: _wrap_tag_result(_io.write(path, content)),  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.list_dir", lambda path: _wrap_tag_result(_io.list_dir(path))  # type: ignore[union-attr]
        )

    # --- http.* ---
    if http_backend is not None:
        _http = http_backend
        env.register_builtin(
            "http.get", lambda url: _wrap_tag_result(_http.get(url))  # type: ignore[union-attr]
        )

    # --- plugin.* ---
    def _plugin_exec(command: str, args: object = None) -> object:
        if env._active_plugin_dir is None:
            raise LumonError("plugin.exec can only be called from a plugin implementation")
        return exec_plugin_script(
            env._active_plugin_dir, command, args,
            executor=env._plugin_executor,
            instance=env._active_plugin_instance or "",
            env_vars=env._active_plugin_env,
        )

    env.register_builtin("plugin.exec", _plugin_exec)
