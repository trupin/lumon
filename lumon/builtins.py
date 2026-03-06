"""Built-in function implementations for all Lumon namespaces."""

from __future__ import annotations

import concurrent.futures
import csv as _csv_mod
import fnmatch
import io as _io_mod
import json as _json_mod
import math
import random
import re as _re
import time as _time
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from urllib.parse import quote, unquote

from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal
from lumon.plugins import exec_plugin_script
from lumon.serializer import deserialize, serialize
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
        if math.isfinite(value) and value == int(value):
            return str(int(value))
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


def _number_sqrt(n: float) -> float:
    try:
        return math.sqrt(n)
    except ValueError:
        raise LumonError("math domain error: sqrt of negative number") from None


def _number_log(n: float) -> float:
    try:
        return math.log(n)
    except ValueError:
        raise LumonError("math domain error: log of non-positive number") from None


def _number_to_text(n: object) -> str:
    if isinstance(n, float) and math.isfinite(n) and n == int(n):
        return str(int(n))
    return str(n)


def _number_format(n: object, decimals: object) -> str:
    if not isinstance(decimals, (int, float)):
        raise LumonError("number.format: decimals must be a number")
    d = int(decimals)
    if not isinstance(n, (int, float)):
        raise LumonError("number.format: first argument must be a number")
    return f"{n:.{d}f}"


_RANGE_CAP = 10000


def _number_range(start: float, end: float) -> list[int]:
    s, e = int(start), int(end)
    if e - s + 1 > _RANGE_CAP:
        raise LumonError(f"number.range: range too large (max {_RANGE_CAP} elements)")
    return list(range(s, e + 1))


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


def _list_group_by(items: list, f: object) -> dict:
    result: dict[str, list] = {}
    for item in items:
        key = _call_fn(f, [item])
        if not isinstance(key, str):
            raise LumonError("list.group_by: key function must return text")
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result


def _list_unique_by(items: list, f: object) -> list:
    seen: list = []
    result: list = []
    for item in items:
        key = _call_fn(f, [item])
        found = False
        for s in seen:
            if key == s:
                found = True
                break
        if not found:
            seen.append(key)
            result.append(item)
    return result


_TIME_CAP_MS = 60000


def _time_wait(ms: float) -> None:
    if ms < 0:
        raise LumonError("time.wait: ms must not be negative")
    if ms > _TIME_CAP_MS:
        raise LumonError("time.wait: ms exceeds 60000ms cap")
    _time.sleep(ms / 1000)


def _time_format(timestamp: float, pattern: str) -> str:
    try:
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        return dt.strftime(pattern)
    except (ValueError, OSError) as exc:
        raise LumonError(f"time.format: {exc}") from None


def _time_parse(text: str, pattern: str) -> object:
    try:
        dt = datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        return dt.timestamp() * 1000
    except (ValueError, OverflowError):
        return None


def _time_date() -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "second": now.second,
    }


def _time_timeout(ms: float, fn_val: object) -> LumonTag:
    if ms < 0:
        raise LumonError("time.timeout: ms must not be negative")
    if ms > _TIME_CAP_MS:
        raise LumonError("time.timeout: ms exceeds 60000ms cap")

    exc_holder: list[Exception] = []

    def _run() -> object:
        try:
            return _call_fn(fn_val, [])
        except (LumonError, AskSignal, ReturnSignal) as e:
            exc_holder.append(e)
            raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            result = future.result(timeout=ms / 1000)
            return LumonTag("ok", result)
        except concurrent.futures.TimeoutError:
            return LumonTag("timeout")
        except Exception as exc:
            if exc_holder:
                raise exc_holder[0] from exc
            raise


def _wrap_tag_result(backend_result: dict) -> LumonTag:
    """Convert a MockFS/MockHTTP dict result to a LumonTag."""
    tag_name = backend_result.get("tag", "error")
    payload = backend_result.get("value")
    return LumonTag(tag_name, payload)


def _text_join(items: object, sep: object) -> str:
    if not isinstance(items, list):
        raise LumonError(f"text.join: expected list, got {type(items).__name__}")
    if not isinstance(sep, str):
        raise LumonError(f"text.join: expected text separator, got {type(sep).__name__}")
    for i, item in enumerate(items):
        if not isinstance(item, str):
            raise LumonError(
                f"text.join: item at index {i} is {type(item).__name__}, expected text"
            )
    return sep.join(items)


def _text_match(s: str, pattern: str) -> bool:
    return fnmatch.fnmatch(s, pattern)


def _text_index_of(s: str, sub: str) -> object:
    idx = s.find(sub)
    return None if idx == -1 else idx


def _text_split_first(s: str, sep: str) -> dict:
    idx = s.find(sep)
    if idx == -1:
        return {"before": s, "after": ""}
    return {"before": s[:idx], "after": s[idx + len(sep):]}


def _text_extract(s: str, start: str, end: str) -> list[str]:
    if not start or not end:
        raise LumonError("text.extract: delimiters must not be empty")
    results: list[str] = []
    i = 0
    while i < len(s):
        si = s.find(start, i)
        if si == -1:
            break
        ei = s.find(end, si + len(start))
        if ei == -1:
            break
        results.append(s[si + len(start):ei])
        i = ei + len(end)
    return results


def _text_pad_start(s: str, length: float, fill: str) -> str:
    if not fill:
        raise LumonError("text.pad_start: fill must not be empty")
    target = int(length)
    if len(s) >= target:
        return s
    pad_needed = target - len(s)
    full_pad = (fill * ((pad_needed // len(fill)) + 1))[:pad_needed]
    return full_pad + s


def _text_pad_end(s: str, length: float, fill: str) -> str:
    if not fill:
        raise LumonError("text.pad_end: fill must not be empty")
    target = int(length)
    if len(s) >= target:
        return s
    pad_needed = target - len(s)
    full_pad = (fill * ((pad_needed // len(fill)) + 1))[:pad_needed]
    return s + full_pad


def _map_from_entries(entries: list) -> dict:
    result: dict[str, object] = {}
    for e in entries:
        if not isinstance(e, dict) or "key" not in e or "value" not in e:
            raise LumonError("map.from_entries: each entry must have 'key' and 'value' fields")
        result[e["key"]] = e["value"]
    return result


def _text_decode_base64(s: str) -> str:
    try:
        return b64decode(s).decode()
    except Exception as e:
        raise LumonError(f"text.decode_base64: invalid base64 input: {e}") from None


def _is_truthy_for_filter(value: object) -> bool:
    return is_truthy(value)


_NAMED_PATTERNS: dict[str, _re.Pattern[str]] = {
    "email": _re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "url": _re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\\]"),
    "iso_date": _re.compile(r"\d{4}-\d{2}-\d{2}"),
    "phone": _re.compile(r"\+?\d[\d\s\-()]{6,}\d"),
    "number": _re.compile(r"-?\d+(?:\.\d+)?"),
}


def _text_match_pattern(s: str, pattern_tag: object) -> bool:
    if not isinstance(pattern_tag, LumonTag):
        raise LumonError("text.match_pattern: second argument must be a tag (e.g. :email)")
    pat = _NAMED_PATTERNS.get(pattern_tag.name)
    if pat is None:
        raise LumonError(
            f"text.match_pattern: unknown pattern :{pattern_tag.name}. "
            f"Available: {', '.join(':' + k for k in _NAMED_PATTERNS)}"
        )
    return pat.fullmatch(s) is not None


def _text_find_pattern(s: str, pattern_tag: object) -> list[str]:
    if not isinstance(pattern_tag, LumonTag):
        raise LumonError("text.find_pattern: second argument must be a tag (e.g. :email)")
    pat = _NAMED_PATTERNS.get(pattern_tag.name)
    if pat is None:
        raise LumonError(
            f"text.find_pattern: unknown pattern :{pattern_tag.name}. "
            f"Available: {', '.join(':' + k for k in _NAMED_PATTERNS)}"
        )
    return pat.findall(s)


# --- json helpers ---

def _json_parse(s: str) -> LumonTag:
    try:
        raw = _json_mod.loads(s)
        return LumonTag("ok", deserialize(raw))
    except (_json_mod.JSONDecodeError, TypeError) as e:
        return LumonTag("error", str(e))


def _json_to_text(value: object) -> str:
    try:
        return _json_mod.dumps(serialize(value), separators=(",", ":"))
    except (TypeError, ValueError) as e:
        raise LumonError(f"json.to_text: cannot serialize value: {e}") from None


def _json_to_text_pretty(value: object) -> str:
    try:
        return _json_mod.dumps(serialize(value), indent=2)
    except (TypeError, ValueError) as e:
        raise LumonError(f"json.to_text_pretty: cannot serialize value: {e}") from None


# --- csv helpers ---

def _csv_parse(s: str) -> list[list[str]]:
    return list(_csv_mod.reader(_io_mod.StringIO(s)))


def _csv_parse_with_headers(s: str) -> list[dict[str, str]]:
    reader = _csv_mod.DictReader(_io_mod.StringIO(s))
    rows: list[dict[str, str]] = []
    for row in reader:
        # DictReader produces None for missing fields and None key for extras
        clean = {k: (v if v is not None else "") for k, v in row.items() if k is not None}
        rows.append(clean)
    return rows


def _csv_to_text(rows: list[list[str]]) -> str:
    out = _io_mod.StringIO()
    writer = _csv_mod.writer(out)
    writer.writerows(rows)
    return out.getvalue()


def _csv_to_text_with_headers(headers: list[str], rows: list[dict[str, str]]) -> str:
    out = _io_mod.StringIO()
    writer = _csv_mod.DictWriter(out, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def register_builtins(
    env: Environment,
    io_backend: object | None = None,
    git_backend: object | None = None,
) -> None:
    """Register all built-in functions in the environment."""

    # --- text.* ---
    env.register_builtin("text.split", lambda s, sep: s.split(sep))
    env.register_builtin("text.join", _text_join)
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
    env.register_builtin("text.match", _text_match)
    env.register_builtin("text.index_of", _text_index_of)
    env.register_builtin("text.lines", lambda s: s.split("\n"))
    env.register_builtin("text.split_first", _text_split_first)
    env.register_builtin("text.extract", _text_extract)
    env.register_builtin("text.pad_start", _text_pad_start)
    env.register_builtin("text.pad_end", _text_pad_end)
    env.register_builtin("text.encode_url", lambda s: quote(s, safe=""))
    env.register_builtin("text.decode_url", lambda s: unquote(s))
    env.register_builtin("text.encode_base64", lambda s: b64encode(s.encode()).decode())
    env.register_builtin("text.decode_base64", _text_decode_base64)
    env.register_builtin("text.match_pattern", _text_match_pattern)
    env.register_builtin("text.find_pattern", _text_find_pattern)

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
    env.register_builtin(
        "list.find",
        lambda items, f: next((x for x in items if is_truthy(_call_fn(f, [x]))), None),
    )
    env.register_builtin(
        "list.any",
        lambda items, f: any(is_truthy(_call_fn(f, [x])) for x in items),
    )
    env.register_builtin(
        "list.all",
        lambda items, f: all(is_truthy(_call_fn(f, [x])) for x in items),
    )
    env.register_builtin(
        "list.zip",
        lambda a, b: [{"first": x, "second": y} for x, y in zip(a, b)],
    )
    env.register_builtin(
        "list.enumerate",
        lambda items: [{"index": i, "value": v} for i, v in enumerate(items)],
    )
    env.register_builtin("list.group_by", _list_group_by)
    env.register_builtin(
        "list.index_of",
        lambda items, item: next((i for i, x in enumerate(items) if x == item), None),
    )
    env.register_builtin("list.unique_by", _list_unique_by)

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
    env.register_builtin(
        "map.map",
        lambda m, f: {k: _call_fn(f, [k, v]) for k, v in m.items()},
    )
    env.register_builtin(
        "map.filter",
        lambda m, f: {k: v for k, v in m.items() if is_truthy(_call_fn(f, [k, v]))},
    )
    env.register_builtin("map.from_entries", _map_from_entries)
    env.register_builtin("map.size", lambda m: len(m))

    # --- number.* ---
    env.register_builtin("number.round", lambda n: round(n))
    env.register_builtin("number.floor", lambda n: math.floor(n))
    env.register_builtin("number.ceil", lambda n: math.ceil(n))
    env.register_builtin("number.abs", lambda n: abs(n))
    env.register_builtin("number.min", lambda a, b: min(a, b))
    env.register_builtin("number.max", lambda a, b: max(a, b))
    env.register_builtin("number.parse", _number_parse)
    env.register_builtin("number.random", lambda: random.random())
    env.register_builtin("number.random_int", lambda lo, hi: random.randint(int(lo), int(hi)))
    env.register_builtin("number.mod", lambda a, b: a % b)
    env.register_builtin("number.pow", lambda base, exp: math.pow(base, exp))
    env.register_builtin("number.sqrt", _number_sqrt)
    env.register_builtin("number.log", _number_log)
    env.register_builtin("number.sign", lambda n: (n > 0) - (n < 0))
    env.register_builtin("number.truncate", lambda n: math.trunc(n))
    env.register_builtin("number.clamp", lambda n, lo, hi: max(lo, min(hi, n)))
    env.register_builtin("number.to_text", _number_to_text)
    env.register_builtin("number.format", _number_format)
    env.register_builtin("number.range", _number_range)
    env.register_builtin("number.pi", lambda: math.pi)
    env.register_builtin("number.e", lambda: math.e)
    env.register_builtin("number.inf", lambda: math.inf)

    # --- type.* ---
    env.register_builtin("type.of", _type_of)
    env.register_builtin("type.is", _type_is)

    # --- time.* ---
    env.register_builtin("time.now", lambda: _time.time() * 1000)
    env.register_builtin("time.wait", _time_wait)
    env.register_builtin("time.format", _time_format)
    env.register_builtin("time.parse", _time_parse)
    env.register_builtin("time.since", lambda ts: _time.time() * 1000 - ts)
    env.register_builtin("time.date", _time_date)
    env.register_builtin("time.add", lambda ts, ms: ts + ms)
    env.register_builtin("time.diff", lambda a, b: a - b)
    env.register_builtin("time.timeout", _time_timeout)

    # --- json.* (pure) ---
    env.register_builtin("json.parse", _json_parse)
    env.register_builtin("json.to_text", _json_to_text)
    env.register_builtin("json.to_text_pretty", _json_to_text_pretty)

    # --- csv.* (pure) ---
    env.register_builtin("csv.parse", _csv_parse)
    env.register_builtin("csv.parse_with_headers", _csv_parse_with_headers)
    env.register_builtin("csv.to_text", _csv_to_text)
    env.register_builtin("csv.to_text_with_headers", _csv_to_text_with_headers)

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
        env.register_builtin(
            "io.delete", lambda path: _wrap_tag_result(_io.delete(path))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.find", lambda path, pattern: _wrap_tag_result(_io.find(path, pattern))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.grep", lambda path, pattern: _wrap_tag_result(_io.grep(path, pattern))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.head", lambda path, n: _wrap_tag_result(_io.head(path, n))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.tail", lambda path, n: _wrap_tag_result(_io.tail(path, n))  # type: ignore[union-attr]
        )
        env.register_builtin(
            "io.replace",
            lambda path, old, new: _wrap_tag_result(_io.replace(path, old, new)),  # type: ignore[union-attr]
        )

        # --- json.read/write (sandboxed via io) ---
        def _json_read(path: str) -> LumonTag:
            result = _io.read(path)  # type: ignore[union-attr]
            if result.get("tag") != "ok":
                return _wrap_tag_result(result)
            content = result.get("value", "")
            return _json_parse(content)

        def _json_write(path: str, value: object) -> LumonTag:
            content = _json_to_text(value)
            return _wrap_tag_result(_io.write(path, content))  # type: ignore[union-attr]

        def _json_write_pretty(path: str, value: object) -> LumonTag:
            content = _json_to_text_pretty(value)
            return _wrap_tag_result(_io.write(path, content))  # type: ignore[union-attr]

        env.register_builtin("json.read", _json_read)
        env.register_builtin("json.write", _json_write)
        env.register_builtin("json.write_pretty", _json_write_pretty)

        # --- csv.read/write (sandboxed via io) ---
        def _csv_read(path: str) -> LumonTag:
            result = _io.read(path)  # type: ignore[union-attr]
            if result.get("tag") != "ok":
                return _wrap_tag_result(result)
            return LumonTag("ok", _csv_parse(result.get("value", "")))

        def _csv_read_with_headers(path: str) -> LumonTag:
            result = _io.read(path)  # type: ignore[union-attr]
            if result.get("tag") != "ok":
                return _wrap_tag_result(result)
            return LumonTag("ok", _csv_parse_with_headers(result.get("value", "")))

        def _csv_write(path: str, rows: list[list[str]]) -> LumonTag:
            content = _csv_to_text(rows)
            return _wrap_tag_result(_io.write(path, content))  # type: ignore[union-attr]

        def _csv_write_with_headers(
            path: str, headers: list[str], rows: list[dict[str, str]],
        ) -> LumonTag:
            content = _csv_to_text_with_headers(headers, rows)
            return _wrap_tag_result(_io.write(path, content))  # type: ignore[union-attr]

        env.register_builtin("csv.read", _csv_read)
        env.register_builtin("csv.read_with_headers", _csv_read_with_headers)
        env.register_builtin("csv.write", _csv_write)
        env.register_builtin("csv.write_with_headers", _csv_write_with_headers)

    # --- git.* ---
    if git_backend is not None:
        _git = git_backend
        env.register_builtin(
            "git.status", lambda: _wrap_tag_result(_git.status())  # type: ignore[union-attr]
        )
        env.register_builtin(
            "git.log", lambda n: _wrap_tag_result(_git.log(n))  # type: ignore[union-attr]
        )

    # --- plugin.* ---
    def _plugin_exec(command: str, args: object = None) -> object:
        plugin_dir = env._active_plugin["dir"]
        if not isinstance(plugin_dir, str):
            raise LumonError("plugin.exec can only be called from a plugin implementation")
        instance = env._active_plugin["instance"]
        plugin_env = env._active_plugin["env"]
        return exec_plugin_script(
            plugin_dir, command, args,
            executor=env._plugin_executor,
            instance=instance if isinstance(instance, str) else "",
            env_vars=plugin_env if isinstance(plugin_env, dict) else None,
        )

    env.register_builtin("plugin.exec", _plugin_exec)

    # --- log ---
    def _log(value: object) -> None:
        env._logs.append(serialize(value))

    env.register_builtin("log", _log)
