"""Tree-walking evaluator for Lumon AST nodes."""

from __future__ import annotations

from lumon.ast_nodes import (
    AskExpr,
    AssertStatement,
    BinaryOp,
    BindPattern,
    Block,
    BoolLiteral,
    DefineBlock,
    FieldAccess,
    FunctionCall,
    IfElseExpr,
    IfStatement,
    ImplementBlock,
    IndexAccess,
    InterpolatedText,
    Lambda,
    LambdaCall,
    LetBinding,
    ListLiteral,
    ListPattern,
    LiteralPattern,
    MapEntry,
    MapLiteral,
    MapPattern,
    MatchArm,
    MatchExpr,
    NoneLiteral,
    NumberLiteral,
    ParamDef,
    PipeOp,
    Program,
    ReturnStatement,
    SpawnExpr,
    SpreadEntry,
    TagLiteral,
    TagPattern,
    TestBlock,
    TextLiteral,
    UnaryOp,
    VarRef,
    WildcardPattern,
    WithExpr,
)
from lumon.environment import Environment
from lumon.errors import AskSignal, LumonError, ReturnSignal, SpawnBatchSignal
from lumon.plugins import validate_contracts
from lumon.serializer import serialize
from lumon.values import LumonFunction, LumonTag, is_truthy


def eval_node(node: object, env: Environment) -> object:
    """Evaluate an AST node and return a Lumon runtime value."""
    match node:
        # --- Literals ---
        case NumberLiteral(value=v):
            return v
        case TextLiteral(value=v):
            return v
        case InterpolatedText(parts=parts):
            return _eval_interpolated(parts, env)
        case BoolLiteral(value=v):
            return v
        case NoneLiteral():
            return None
        case ListLiteral(elements=elts):
            return [eval_node(e, env) for e in elts]
        case MapLiteral(entries=entries):
            return _eval_map_literal(entries, env)
        case TagLiteral(name=name, payload=payload):
            p = eval_node(payload, env) if payload is not None else None
            return LumonTag(name, p)

        # --- Bindings ---
        case LetBinding(name=name, value=value):
            env.set(name, eval_node(value, env))
            return None
        case VarRef(name=name):
            return env.get(name)

        # --- Return ---
        case ReturnStatement(value=value):
            raise ReturnSignal(eval_node(value, env))

        # --- Operators ---
        case BinaryOp():
            return _eval_binary(node, env)
        case UnaryOp():
            return _eval_unary(node, env)
        case PipeOp():
            return _eval_pipe(node, env)

        # --- Access ---
        case FieldAccess(obj=obj_node, field=field):
            return _eval_field_access(obj_node, field, env)
        case IndexAccess(obj=obj_node, index=idx_node):
            return _eval_index_access(obj_node, idx_node, env)

        # --- Function calls ---
        case FunctionCall(target=target, args=args):
            return _eval_function_call(target, args, env)
        case LambdaCall(target=target, args=args):
            return _eval_lambda_call(target, args, env)

        # --- Lambda ---
        case Lambda(params=params, body=body):
            return LumonFunction(params, body, env.snapshot())

        # --- Block ---
        case Block(statements=stmts):
            return _eval_block(stmts, env)

        # --- Control flow ---
        case IfElseExpr(condition=cond, then_expr=then_e, else_expr=else_e):
            return eval_node(then_e, env) if is_truthy(eval_node(cond, env)) else eval_node(else_e, env)
        case IfStatement(condition=cond, body=body, else_body=else_body):
            if is_truthy(eval_node(cond, env)):
                return eval_node(body, env)
            if else_body is not None:
                return eval_node(else_body, env)
            return None
        case MatchExpr():
            return _eval_match(node, env)
        case WithExpr():
            return _eval_with(node, env)

        # --- Define / Implement / Test ---
        case DefineBlock():
            env.register_define(node)
            return None
        case ImplementBlock():
            env.register_implement(node)
            return None
        case TestBlock():
            env.register_test(node)
            return None
        case AssertStatement(expr=expr):
            val = eval_node(expr, env)
            if not is_truthy(val):
                raise LumonError("Assertion failed")
            return None

        # --- Coroutines ---
        case AskExpr():
            return _eval_ask(node, env)
        case SpawnExpr():
            return _eval_spawn(node, env)

        # --- Program ---
        case Program(statements=stmts):
            return _eval_program(stmts, env)

        case _:
            raise LumonError(f"Unknown AST node type: {type(node).__name__}")


def _eval_program(stmts: tuple[object, ...], env: Environment) -> object:
    """Evaluate top-level program statements."""
    result = None
    for stmt in stmts:
        result = eval_node(stmt, env)
    return result


def _eval_block(stmts: tuple[object, ...], env: Environment) -> object:
    """Evaluate a block of statements; return value of last expression."""
    result = None
    for stmt in stmts:
        result = eval_node(stmt, env)
    return result


def _eval_map_literal(entries: tuple[object, ...], env: Environment) -> dict:
    result: dict[str, object] = {}
    for entry in entries:
        match entry:
            case MapEntry(key=k, value=v):
                result[k] = eval_node(v, env)
            case SpreadEntry(expr=expr):
                spread_val = eval_node(expr, env)
                if isinstance(spread_val, dict):
                    result.update(spread_val)
                else:
                    raise LumonError("Spread operator requires a map value")
    return result


def _eval_interpolated(parts: tuple[object, ...], env: Environment) -> str:
    """Evaluate an interpolated string."""
    result_parts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            result_parts.append(part)
        else:
            val = eval_node(part, env)
            result_parts.append(_value_to_text(val))
    return "".join(result_parts)


def _value_to_text(value: object) -> str:
    """Convert a Lumon value to text (like text.from)."""
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
        if value == int(value) and not (value == 0 and str(value).startswith("-")):
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        inner = ", ".join(_value_to_text(item) for item in value)
        return f"[{inner}]"
    if isinstance(value, dict):
        entries = ", ".join(f"{k}: {_value_to_text(v)}" for k, v in value.items())
        return "{" + entries + "}"
    if isinstance(value, LumonTag):
        if value.payload is None:
            return f":{value.name}"
        return f":{value.name}({_value_to_text(value.payload)})"
    return str(value)


# --- Operators ---

def _eval_binary(node: BinaryOp, env: Environment) -> object:
    op = node.op
    # Short-circuit operators
    if op == "and":
        left = eval_node(node.left, env)
        return left if not is_truthy(left) else eval_node(node.right, env)
    if op == "or":
        left = eval_node(node.left, env)
        return left if is_truthy(left) else eval_node(node.right, env)
    if op == "??":
        left = eval_node(node.left, env)
        return left if left is not None else eval_node(node.right, env)

    left = eval_node(node.left, env)
    right = eval_node(node.right, env)

    match op:
        case "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
            raise LumonError(f"Cannot add {_type_name(left)} and {_type_name(right)}")
        case "-":
            return left - right  # type: ignore[operator]
        case "*":
            return left * right  # type: ignore[operator]
        case "/":
            if isinstance(right, (int, float)) and right == 0:
                raise LumonError("Division by zero")
            return left / right  # type: ignore[operator]
        case "%":
            return left % right  # type: ignore[operator]
        case "==":
            return _values_equal(left, right)
        case "!=":
            return not _values_equal(left, right)
        case "<":
            return left < right  # type: ignore[operator]
        case ">":
            return left > right  # type: ignore[operator]
        case "<=":
            return left <= right  # type: ignore[operator]
        case ">=":
            return left >= right  # type: ignore[operator]
        case _:
            raise LumonError(f"Unknown operator: {op}")


def _eval_unary(node: UnaryOp, env: Environment) -> object:
    val = eval_node(node.operand, env)
    match node.op:
        case "not":
            return not is_truthy(val)
        case "-":
            return -val  # type: ignore[operator]
        case _:
            raise LumonError(f"Unknown unary operator: {node.op}")


def _values_equal(a: object, b: object) -> bool:
    """Deep equality for Lumon values."""
    if isinstance(a, LumonTag) and isinstance(b, LumonTag):
        return a.name == b.name and _values_equal(a.payload, b.payload)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_values_equal(a[k], b[k]) for k in a)
    # Handle None equality
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a == b


def _type_name(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, LumonTag):
        return "tag"
    if isinstance(value, LumonFunction):
        return "function"
    return type(value).__name__


# --- Access ---

def _eval_field_access(obj_node: object, field: str, env: Environment) -> object:
    # Check if this is a namespace function reference
    if isinstance(obj_node, VarRef) and env.is_namespace(obj_node.name):
        ns_path = f"{obj_node.name}.{field}"
        # Return a reference to the namespace function (for pipe, etc.)
        try:
            resolved = env.resolve_function(ns_path)
            if resolved[0] == "builtin":
                return resolved[1]
            # User-defined function reference
            return _make_user_fn_ref(ns_path, env)
        except LumonError:
            pass  # Fall through to field access

    obj = eval_node(obj_node, env)
    if isinstance(obj, dict):
        if field in obj:
            return obj[field]
        raise LumonError(f"Field '{field}' not found on map")
    return None  # Non-map field access returns none (safe for ?? fallback)


def _make_user_fn_ref(ns_path: str, env: Environment) -> LumonFunction:
    """Create a callable reference to a user-defined function."""
    resolved = env.resolve_function(ns_path)
    define = resolved[1]
    impl = resolved[2]
    # Create a LumonFunction that wraps the implement call
    params = tuple(p.name for p in define.params) if define else ()  # type: ignore[union-attr]
    return LumonFunction(params, impl, env.snapshot(), is_lambda=False)


def _eval_index_access(obj_node: object, idx_node: object, env: Environment) -> object:
    obj = eval_node(obj_node, env)
    idx = eval_node(idx_node, env)
    if isinstance(obj, list):
        if isinstance(idx, (int, float)):
            i = int(idx)
            if 0 <= i < len(obj):
                return obj[i]
            raise LumonError(f"Index {i} out of bounds for list of length {len(obj)}")
        raise LumonError(f"List index must be a number, got {_type_name(idx)}")
    raise LumonError(f"Cannot index {_type_name(obj)}")


# --- Pipe ---

def _eval_pipe(node: PipeOp, env: Environment) -> object:
    value = eval_node(node.value, env)
    target = node.target

    match target:
        case FunctionCall(target=name, args=args):
            # Prepend piped value to args
            evaluated_args = tuple(eval_node(a, env) for a in args)
            all_args = (value,) + evaluated_args
            return _call_function(name, all_args, env)
        case VarRef(name=name):
            # Check if it's a namespace function or a lambda variable
            if env.is_namespace(name):
                raise LumonError(f"Cannot pipe to namespace '{name}' — use a specific function")
            fn_val = env.get(name)
            return _call_value(fn_val, (value,), env)
        case Lambda():
            fn_val = eval_node(target, env)
            return _call_value(fn_val, (value,), env)
        case _:
            # Could be a namespace path string (from namespace_ref)
            if isinstance(target, str):
                return _call_function(target, (value,), env)
            # Could be a FieldAccess that resolved to a namespace function
            fn_val = eval_node(target, env)
            if callable(fn_val):
                return fn_val(value)
            return _call_value(fn_val, (value,), env)


# --- Function calls ---

def _eval_function_call(target: str, args: tuple[object, ...], env: Environment) -> object:
    evaluated_args = tuple(eval_node(a, env) for a in args)
    return _call_function(target, evaluated_args, env)


def _eval_lambda_call(target: object, args: tuple[object, ...], env: Environment) -> object:
    fn_val = eval_node(target, env)
    evaluated_args = tuple(eval_node(a, env) for a in args)
    return _call_value(fn_val, evaluated_args, env)


def _call_function(name: str, args: tuple[object, ...], env: Environment) -> object:
    """Call a named function (builtin or user-defined)."""
    resolved = env.resolve_function(name)
    match resolved:
        case ("builtin", fn):
            return fn(*args)  # type: ignore[operator]
        case ("user", define, impl):
            return _call_user_function(name, define, impl, args, env)
        case _:
            raise LumonError(f"Cannot call '{name}'")


def _inject_forced_args(
    define: DefineBlock,
    agent_args: tuple[object, ...],
    forced_values: dict[str, object],
    name: str,
) -> tuple[object, ...]:
    """Reconstruct full args by interleaving forced values at correct positions.

    Walk define params in order. For each param:
    - If forced → insert forced value
    - Otherwise → consume next agent-provided arg

    Validates that agent provided the right number of args (total - forced).
    """
    visible_count = len(define.params) - len(forced_values) if define.params else 0

    if len(agent_args) > visible_count:
        raise LumonError(
            f"Too many arguments in call to {name}: "
            f"expected at most {visible_count}, got {len(agent_args)}",
            function=name,
        )

    full_args: list[object] = []
    agent_idx = 0
    if define.params:
        for param in define.params:
            assert isinstance(param, ParamDef)
            if param.name in forced_values:
                full_args.append(forced_values[param.name])
            elif agent_idx < len(agent_args):
                full_args.append(agent_args[agent_idx])
                agent_idx += 1
            else:
                break  # remaining params will use defaults in param binding
    return tuple(full_args)


def _call_user_function(
    name: str, define: object, impl: object, args: tuple[object, ...], env: Environment
) -> object:
    """Call a user-defined function (define + implement)."""
    assert isinstance(impl, ImplementBlock)

    # Plugin forced value injection + contract validation + context injection
    plugin_dir = env._plugin_dirs.get(name)
    if plugin_dir is not None and isinstance(define, DefineBlock):
        # Inject forced values before contract validation
        forced = env._plugin_forced_values.get(name, {})
        if forced:
            args = _inject_forced_args(define, args, forced, name)

        contracts = env._plugin_contracts.get(name, {})
        if contracts:
            validate_contracts(name, args, define, contracts)

    env.push_call(name)
    try:
        child_env = env.child_scope()

        # Bind parameters
        if isinstance(define, DefineBlock) and define.params:
            for i, param in enumerate(define.params):
                assert isinstance(param, ParamDef)
                if i < len(args):
                    child_env.set(param.name, args[i])
                elif param.default is not None:
                    child_env.set(param.name, eval_node(param.default, env))
                else:
                    raise LumonError(
                        f"Missing argument '{param.name}' in call to {name}",
                        function=name,
                    )

        # Set plugin context so plugin.exec works inside plugin impls
        # Uses shared mutable dict so nested calls (implement → plugin) see updates
        prev_plugin_dir = env._active_plugin["dir"]
        prev_plugin_instance = env._active_plugin["instance"]
        prev_plugin_env = env._active_plugin["env"]
        if plugin_dir is not None:
            instance = env._plugin_instances.get(name) or ""
            env._active_plugin["dir"] = plugin_dir
            env._active_plugin["instance"] = instance
            env._active_plugin["env"] = env._plugin_env_vars.get(name) or None
            # Track that this plugin instance was used (for shutdown signaling)
            env._used_plugins.add((plugin_dir, instance))

        try:
            result = None
            for stmt in impl.body:
                result = eval_node(stmt, child_env)
            return result
        except ReturnSignal as rs:
            return rs.value
        finally:
            if plugin_dir is not None:
                env._active_plugin["dir"] = prev_plugin_dir
                env._active_plugin["instance"] = prev_plugin_instance
                env._active_plugin["env"] = prev_plugin_env
    except LumonError as e:
        if e.function is None:
            e.function = name
        if not e.trace:
            e.trace = list(env._call_stack)
        raise
    finally:
        env.pop_call()


def _call_value(fn_val: object, args: tuple[object, ...], env: Environment) -> object:
    """Call a function value (LumonFunction or Python callable)."""
    if callable(fn_val) and not isinstance(fn_val, LumonFunction):
        return fn_val(*args)
    if isinstance(fn_val, LumonFunction):
        return _call_lumon_function(fn_val, args, env)
    raise LumonError(f"Cannot call value of type {_type_name(fn_val)}")


def call_lumon_fn(fn_val: LumonFunction, args: list[object]) -> object:
    """Public interface for calling a LumonFunction (used by builtins)."""
    return _call_lumon_function(fn_val, tuple(args), None)


def _call_lumon_function(
    fn: LumonFunction, args: tuple[object, ...], _caller_env: Environment | None
) -> object:
    """Execute a LumonFunction (lambda or implement-based)."""
    child_env = fn.closure_env.child_scope()  # type: ignore[union-attr]

    for i, param in enumerate(fn.params):
        if i < len(args):
            child_env.set(param, args[i])

    if fn.is_lambda:
        # Lambda: evaluate body, return result (last expression value)
        try:
            return eval_node(fn.body, child_env)
        except ReturnSignal as rs:
            return rs.value
    else:
        # Implement block: explicit return required
        try:
            result = None
            if isinstance(fn.body, ImplementBlock):
                for stmt in fn.body.body:
                    result = eval_node(stmt, child_env)
            else:
                result = eval_node(fn.body, child_env)
            return result
        except ReturnSignal as rs:
            return rs.value


# --- Match ---

def _eval_match(node: MatchExpr, env: Environment) -> object:
    subject = eval_node(node.subject, env)
    for arm in node.arms:
        assert isinstance(arm, MatchArm)
        bindings = _match_pattern(arm.pattern, subject)
        if bindings is not None:
            # Check guard
            if arm.guard is not None:
                guard_env = env.child_scope()
                for name, val in bindings.items():
                    guard_env.set(name, val)
                if not is_truthy(eval_node(arm.guard, guard_env)):
                    continue
            # Match succeeded
            match_env = env.child_scope()
            for name, val in bindings.items():
                match_env.set(name, val)
            return eval_node(arm.body, match_env)
    raise LumonError("Non-exhaustive match: no pattern matched")


def _match_pattern(pattern: object, value: object) -> dict[str, object] | None:
    """Try to match a pattern against a value. Returns bindings dict or None."""
    match pattern:
        case WildcardPattern():
            return {}
        case BindPattern(name=name):
            return {name: value}
        case LiteralPattern(value=lit):
            if _values_equal(_literal_to_value(lit), value):
                return {}
            return None
        case TagPattern(name=name, payload_pattern=pp):
            if not isinstance(value, LumonTag) or value.name != name:
                return None
            if pp is None:
                return {}
            return _match_pattern(pp, value.payload)
        case MapPattern(entries=entries):
            if not isinstance(value, dict):
                return None
            bindings: dict[str, object] = {}
            for key, pat in entries:
                if key not in value:
                    return None
                result = _match_pattern(pat, value[key])
                if result is None:
                    return None
                bindings.update(result)
            return bindings
        case ListPattern(elements=elts, rest_name=rest):
            if not isinstance(value, list):
                return None
            if rest is not None:
                if len(value) < len(elts):
                    return None
                bindings = {}
                for i, pat in enumerate(elts):
                    result = _match_pattern(pat, value[i])
                    if result is None:
                        return None
                    bindings.update(result)
                bindings[rest] = value[len(elts) :]
                return bindings
            if len(value) != len(elts):
                return None
            bindings = {}
            for i, pat in enumerate(elts):
                result = _match_pattern(pat, value[i])
                if result is None:
                    return None
                bindings.update(result)
            return bindings
        case _:
            return None


def _literal_to_value(lit: object) -> object:
    """Convert a literal pattern value to its runtime equivalent."""
    # Literal patterns store Python values directly
    return lit


# --- With ---

def _eval_with(node: WithExpr, env: Environment) -> object:
    child_env = env.child_scope()
    for name, expr in node.bindings:
        val = eval_node(expr, child_env)
        if val is None:
            return eval_node(node.else_body, env)
        if isinstance(val, LumonTag):
            if val.name == "error":
                return eval_node(node.else_body, env)
            if val.name == "ok":
                val = val.payload
        child_env.set(name, val)
    return eval_node(node.then_body, child_env)


# --- Ask / Spawn ---

def _eval_ask(node: AskExpr, env: Environment) -> object:
    # If a response has been queued (test/replay mode), return it directly.
    queued = env.consume_response()
    if queued is not None:
        return queued[0]

    prompt = eval_node(node.prompt, env) if node.prompt else ""
    context = eval_node(node.context, env) if node.context else None
    expects = node.expects  # Type expression, serialize as-is

    envelope: dict[str, object] = {
        "type": "ask",
        "prompt": prompt,
    }
    if context is not None:
        envelope["context"] = serialize(context)
    if expects is not None:
        envelope["expects"] = expects

    # Daemon mode: block on suspend callback instead of raising
    if env._suspend_callback is not None:
        return env._suspend_callback.suspend_for_ask(envelope)  # type: ignore[union-attr]

    raise AskSignal(envelope)


def _eval_spawn(node: SpawnExpr, env: Environment) -> object:
    tasks = eval_node(node.tasks, env)
    if not isinstance(tasks, list):
        raise LumonError("spawn requires a list of task maps")

    if not tasks:
        return []

    # Test/replay mode: consume responses from queue
    first = env.consume_response()
    if first is not None:
        results: list[object] = [first[0]]
        for _ in range(1, len(tasks)):
            q = env.consume_response()
            if q is None:
                raise LumonError("spawn: not enough mock responses queued")
            results.append(q[0])
        return results

    # Build envelopes
    envelopes: list[dict] = []
    for task in tasks:
        if not isinstance(task, dict):
            raise LumonError("spawn: each task must be a map with a 'prompt' key")
        if "prompt" not in task:
            raise LumonError("spawn: each task must have a 'prompt' key")
        prompt = task["prompt"]
        context = task.get("context")
        fork = task.get("fork")
        expects = task.get("expects")

        envelope: dict[str, object] = {"prompt": prompt}
        if context is not None:
            envelope["context"] = serialize(context)
        if fork:
            envelope["fork"] = fork
        if expects is not None:
            envelope["expects"] = expects
        envelopes.append(envelope)

    # Daemon mode: flush via callback — blocks until all responses arrive
    if env._spawn_flush_callback is not None:
        responses = env._spawn_flush_callback(envelopes)
        return list(responses)

    # Non-daemon mode: signal suspension
    raise SpawnBatchSignal(envelopes)
