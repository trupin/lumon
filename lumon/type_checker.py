"""Static type checker for Lumon — catches type errors before execution."""

from __future__ import annotations

from dataclasses import dataclass

from lumon.ast_nodes import (
    AssertStatement,
    BinaryOp,
    Block,
    BoolLiteral,
    DefineBlock,
    FieldAccess,
    FunctionCall,
    IfElseExpr,
    IfStatement,
    ImplementBlock,
    IndexAccess,
    Lambda,
    LambdaCall,
    LetBinding,
    ListLiteral,
    MapEntry,
    MapLiteral,
    MatchExpr,
    NoneLiteral,
    NumberLiteral,
    ParamDef,
    PipeOp,
    Program,
    ReturnStatement,
    SpreadEntry,
    TagLiteral,
    TestBlock,
    TextLiteral,
    InterpolatedText,
    UnaryOp,
    VarRef,
)
from lumon.errors import LumonError


# ── Type representations ─────────────────────────────────────────────


@dataclass(frozen=True)
class TNumber:
    pass


@dataclass(frozen=True)
class TText:
    pass


@dataclass(frozen=True)
class TBool:
    pass


@dataclass(frozen=True)
class TNone:
    pass


@dataclass(frozen=True)
class TAny:
    pass


@dataclass(frozen=True)
class TList:
    element: object  # LumonType


@dataclass(frozen=True)
class TMap:
    fields: dict[str, object] | None = None  # None = unknown structure


@dataclass(frozen=True)
class TTag:
    name: str
    payload: object | None = None


@dataclass(frozen=True)
class TUnion:
    types: tuple[object, ...]


@dataclass(frozen=True)
class TFn:
    params: tuple[object, ...]
    returns: object  # LumonType


@dataclass(frozen=True)
class TVar:
    name: str


LumonType = (
    TNumber | TText | TBool | TNone | TAny | TList | TMap | TTag | TUnion | TFn | TVar
)


# ── Parse type expressions from AST ─────────────────────────────────


def parse_type_expr(expr: object) -> object:
    """Convert parser type representation (string/dict) to internal type."""
    if expr is None:
        return TAny()
    if isinstance(expr, str):
        return {
            "number": TNumber(),
            "text": TText(),
            "bool": TBool(),
            "none": TNone(),
            "any": TAny(),
        }.get(expr, TAny())
    if isinstance(expr, dict):
        if "union" in expr:
            return TUnion(tuple(parse_type_expr(t) for t in expr["union"]))
        if "tag" in expr:
            payload = parse_type_expr(expr["payload"]) if "payload" in expr else None
            return TTag(expr["tag"], payload)
        if "list" in expr:
            return TList(parse_type_expr(expr["list"]))
        if "struct" in expr:
            return TMap(
                {k: parse_type_expr(v) for k, v in expr["struct"].items()}
            )
        if "fn" in expr:
            params = tuple(parse_type_expr(p) for p in expr["fn"])
            ret = parse_type_expr(expr.get("returns"))
            return TFn(params, ret)
        # Parameterized type like {"list": "number"}
        for key, val in expr.items():
            return TList(parse_type_expr(val)) if key == "list" else TAny()
    return TAny()


# ── Assignability check ──────────────────────────────────────────────


def is_assignable(actual: object, expected: object) -> bool:
    """Check if actual type is assignable to expected type."""
    if isinstance(actual, TAny) or isinstance(expected, TAny):
        return True
    if isinstance(actual, TVar) or isinstance(expected, TVar):
        return True
    if type(actual) is type(expected) and actual == expected:
        return True
    # Union as actual → cannot satisfy concrete expected
    if isinstance(actual, TUnion) and not isinstance(expected, TUnion):
        return False
    # Concrete actual → union expected: check if matches any member
    if isinstance(expected, TUnion):
        return any(is_assignable(actual, m) for m in expected.types)
    # List covariance
    if isinstance(actual, TList) and isinstance(expected, TList):
        return is_assignable(actual.element, expected.element)
    # Tag: same name, payload assignable
    if isinstance(actual, TTag) and isinstance(expected, TTag):
        if actual.name != expected.name:
            return False
        if expected.payload is None:
            return True
        if actual.payload is None:
            return expected.payload is None
        return is_assignable(actual.payload, expected.payload)
    # Same base type (TNumber == TNumber, etc.)
    if type(actual) is type(expected):
        return True
    return False


# ── Builtin type signatures ──────────────────────────────────────────

_A = TVar("a")
_B = TVar("b")

BUILTIN_SIGS: dict[str, tuple[tuple[object, ...], object]] = {
    # text.*
    "text.split": ((TText(), TText()), TList(TText())),
    "text.join": ((TList(TText()), TText()), TText()),
    "text.contains": ((TText(), TText()), TBool()),
    "text.replace": ((TText(), TText(), TText()), TText()),
    "text.slice": ((TText(), TNumber(), TNumber()), TText()),
    "text.length": ((TText(),), TNumber()),
    "text.upper": ((TText(),), TText()),
    "text.lower": ((TText(),), TText()),
    "text.trim": ((TText(),), TText()),
    "text.starts_with": ((TText(), TText()), TBool()),
    "text.ends_with": ((TText(), TText()), TBool()),
    "text.from": ((TAny(),), TText()),
    "text.match": ((TText(), TText()), TBool()),
    "text.index_of": ((TText(), TText()), TUnion((TNumber(), TNone()))),
    "text.lines": ((TText(),), TList(TText())),
    "text.split_first": ((TText(), TText()), TMap()),
    "text.extract": ((TText(), TText(), TText()), TList(TText())),
    "text.pad_start": ((TText(), TNumber(), TText()), TText()),
    "text.pad_end": ((TText(), TNumber(), TText()), TText()),
    # list.*
    "list.map": ((TList(_A), TFn((_A,), _B)), TList(_B)),
    "list.filter": ((TList(_A), TFn((_A,), TBool())), TList(_A)),
    "list.fold": ((TList(_A), _B, TFn((_B, _A), _B)), _B),
    "list.flat_map": ((TList(_A), TFn((_A,), TList(_B))), TList(_B)),
    "list.sort": ((TList(_A),), TList(_A)),
    "list.sort_by": ((TList(_A), TFn((_A,), TAny())), TList(_A)),
    "list.take": ((TList(_A), TNumber()), TList(_A)),
    "list.drop": ((TList(_A), TNumber()), TList(_A)),
    "list.deduplicate": ((TList(_A),), TList(_A)),
    "list.length": ((TList(_A),), TNumber()),
    "list.contains": ((TList(_A), _A), TBool()),
    "list.reverse": ((TList(_A),), TList(_A)),
    "list.flatten": ((TList(TList(_A)),), TList(_A)),
    "list.head": ((TList(_A),), TUnion((_A, TNone()))),
    "list.tail": ((TList(_A),), TList(_A)),
    "list.concat": ((TList(_A), TList(_A)), TList(_A)),
    # map.*
    "map.get": ((TMap(), TText()), TAny()),
    "map.set": ((TMap(), TText(), TAny()), TMap()),
    "map.keys": ((TMap(),), TList(TText())),
    "map.values": ((TMap(),), TList(TAny())),
    "map.merge": ((TMap(), TMap()), TMap()),
    "map.has": ((TMap(), TText()), TBool()),
    "map.remove": ((TMap(), TText()), TMap()),
    "map.entries": ((TMap(),), TList(TMap())),
    # number.*
    "number.round": ((TNumber(),), TNumber()),
    "number.floor": ((TNumber(),), TNumber()),
    "number.ceil": ((TNumber(),), TNumber()),
    "number.abs": ((TNumber(),), TNumber()),
    "number.min": ((TNumber(), TNumber()), TNumber()),
    "number.max": ((TNumber(), TNumber()), TNumber()),
    "number.parse": ((TText(),), TUnion((TNumber(), TNone()))),
    "number.random": ((), TNumber()),
    "number.random_int": ((TNumber(), TNumber()), TNumber()),
    "number.mod": ((TNumber(), TNumber()), TNumber()),
    "number.pow": ((TNumber(), TNumber()), TNumber()),
    "number.sqrt": ((TNumber(),), TNumber()),
    "number.log": ((TNumber(),), TNumber()),
    "number.sign": ((TNumber(),), TNumber()),
    "number.truncate": ((TNumber(),), TNumber()),
    "number.clamp": ((TNumber(), TNumber(), TNumber()), TNumber()),
    "number.to_text": ((TNumber(),), TText()),
    "number.pi": ((), TNumber()),
    "number.e": ((), TNumber()),
    "number.inf": ((), TNumber()),
    # type.*
    "type.of": ((TAny(),), TText()),
    "type.is": ((TAny(), TText()), TBool()),
    # time.*
    "time.now": ((), TNumber()),
    "time.wait": ((TNumber(),), TNone()),
    "time.format": ((TNumber(), TText()), TText()),
    "time.parse": ((TText(), TText()), TUnion((TNumber(), TNone()))),
    "time.since": ((TNumber(),), TNumber()),
    "time.date": ((), TMap()),
    "time.add": ((TNumber(), TNumber()), TNumber()),
    "time.diff": ((TNumber(), TNumber()), TNumber()),
    "time.timeout": ((TNumber(), TFn((), _A)), TUnion((TTag("ok", _A), TTag("timeout")))),
}

IO_SIGS: dict[str, tuple[tuple[object, ...], object]] = {
    "io.read": ((TText(),), TUnion((TTag("ok", TText()), TTag("error", TText())))),
    "io.write": (
        (TText(), TText()),
        TUnion((TTag("ok"), TTag("error", TText()))),
    ),
    "io.list_dir": (
        (TText(),),
        TUnion((TTag("ok", TList(TText())), TTag("error", TText()))),
    ),
    "io.delete": (
        (TText(),),
        TUnion((TTag("ok"), TTag("error", TText()))),
    ),
    "io.find": (
        (TText(), TText()),
        TUnion((TTag("ok", TList(TText())), TTag("error", TText()))),
    ),
    "io.grep": (
        (TText(), TText()),
        TUnion((TTag("ok", TList(TText())), TTag("error", TText()))),
    ),
    "io.head": (
        (TText(), TNumber()),
        TUnion((TTag("ok", TText()), TTag("error", TText()))),
    ),
    "io.tail": (
        (TText(), TNumber()),
        TUnion((TTag("ok", TText()), TTag("error", TText()))),
    ),
    "io.replace": (
        (TText(), TText(), TText()),
        TUnion((TTag("ok"), TTag("error", TText()))),
    ),
}

GIT_SIGS: dict[str, tuple[tuple[object, ...], object]] = {
    "git.status": ((), TUnion((TTag("ok", TText()), TTag("error", TText())))),
    "git.log": (
        (TNumber(),),
        TUnion((TTag("ok", TList(TText())), TTag("error", TText()))),
    ),
}


# ── Type environment ─────────────────────────────────────────────────


class TypeEnv:
    """Tracks variable → type bindings through scope chain."""

    def __init__(self, parent: TypeEnv | None = None) -> None:
        self._bindings: dict[str, object] = {}
        self._parent = parent
        self._defines: dict[str, DefineBlock] = (
            {} if parent is None else parent._defines
        )

    def get(self, name: str) -> object:
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.get(name)
        return TAny()

    def set(self, name: str, typ: object) -> None:
        self._bindings[name] = typ

    def child(self) -> TypeEnv:
        return TypeEnv(parent=self)

    def register_define(self, define: DefineBlock) -> None:
        self._defines[define.namespace_path] = define

    def get_define(self, name: str) -> DefineBlock | None:
        return self._defines.get(name)


# ── Generic resolution ───────────────────────────────────────────────


def _resolve(typ: object, subs: dict[str, object]) -> object:
    """Resolve type variables using substitution map."""
    if isinstance(typ, TVar):
        return subs.get(typ.name, TAny())
    if isinstance(typ, TList):
        return TList(_resolve(typ.element, subs))
    if isinstance(typ, TUnion):
        return TUnion(tuple(_resolve(t, subs) for t in typ.types))
    if isinstance(typ, TFn):
        return TFn(
            tuple(_resolve(p, subs) for p in typ.params), _resolve(typ.returns, subs)
        )
    if isinstance(typ, TTag) and typ.payload is not None:
        return TTag(typ.name, _resolve(typ.payload, subs))
    return typ


def _bind_type_var(
    actual: object, expected: object, subs: dict[str, object]
) -> None:
    """Try to bind type variables from expected against actual types."""
    if isinstance(expected, TVar):
        if expected.name not in subs and not isinstance(actual, TAny):
            subs[expected.name] = actual
        return
    if isinstance(expected, TList) and isinstance(actual, TList):
        _bind_type_var(actual.element, expected.element, subs)
    if isinstance(expected, TFn) and isinstance(actual, TFn):
        for a, e in zip(actual.params, expected.params):
            _bind_type_var(a, e, subs)
        _bind_type_var(actual.returns, expected.returns, subs)


# ── Core checker ─────────────────────────────────────────────────────


def check_node(node: object, env: TypeEnv, sigs: dict[str, tuple[tuple[object, ...], object]]) -> object:
    """Recursively check AST node, returning inferred type. Raises LumonError on type error."""

    if isinstance(node, NumberLiteral):
        return TNumber()

    if isinstance(node, TextLiteral):
        return TText()

    if isinstance(node, InterpolatedText):
        for part in node.parts:
            if not isinstance(part, str):
                check_node(part, env, sigs)
        return TText()

    if isinstance(node, BoolLiteral):
        return TBool()

    if isinstance(node, NoneLiteral):
        return TNone()

    if isinstance(node, ListLiteral):
        if not node.elements:
            return TList(TAny())
        types = [check_node(el, env, sigs) for el in node.elements]
        first = types[0]
        for t in types[1:]:
            if isinstance(first, TAny) or isinstance(t, TAny):
                continue
            if type(first) is not type(t):
                raise LumonError("Type error: mixed types in list literal")
        return TList(first)

    if isinstance(node, MapLiteral):
        fields: dict[str, object] = {}
        for entry in node.entries:
            if isinstance(entry, MapEntry):
                fields[entry.key] = check_node(entry.value, env, sigs)
            elif isinstance(entry, SpreadEntry):
                check_node(entry.expr, env, sigs)
        return TMap(fields)

    if isinstance(node, TagLiteral):
        payload_type = check_node(node.payload, env, sigs) if node.payload else None
        return TTag(node.name, payload_type)

    if isinstance(node, VarRef):
        return env.get(node.name)

    if isinstance(node, LetBinding):
        val_type = check_node(node.value, env, sigs)
        env.set(node.name, val_type)
        return val_type

    if isinstance(node, FieldAccess):
        obj_type = check_node(node.obj, env, sigs)
        if isinstance(obj_type, TMap) and obj_type.fields is not None:
            if node.field in obj_type.fields:
                return obj_type.fields[node.field]
            raise LumonError(f"Type error: field '{node.field}' not found on map")
        if isinstance(obj_type, (TNumber, TText, TBool, TNone, TList)):
            raise LumonError(f"Type error: cannot access field on {type(obj_type).__name__}")
        return TAny()

    if isinstance(node, IndexAccess):
        check_node(node.obj, env, sigs)
        check_node(node.index, env, sigs)
        return TAny()

    if isinstance(node, BinaryOp):
        left_t = check_node(node.left, env, sigs)
        right_t = check_node(node.right, env, sigs)
        if node.op in ("and", "or", "??"):
            return TAny()
        if node.op in ("-", "*", "/", "%"):
            _check_numeric(left_t, right_t, node.op)
            return TNumber()
        if node.op == "+":
            _check_addable(left_t, right_t)
            if isinstance(left_t, TAny) or isinstance(right_t, TAny):
                return TAny()
            if isinstance(left_t, TText):
                return TText()
            return TNumber()
        if node.op in ("<", ">", "<=", ">="):
            _check_comparable(left_t, right_t, node.op)
            return TBool()
        if node.op in ("==", "!="):
            return TBool()
        return TAny()

    if isinstance(node, UnaryOp):
        check_node(node.operand, env, sigs)
        if node.op == "not":
            return TBool()
        if node.op == "-":
            return TNumber()
        return TAny()

    if isinstance(node, PipeOp):
        val_type = check_node(node.value, env, sigs)
        # Pipe target is a FunctionCall — prepend piped value to args
        if isinstance(node.target, FunctionCall):
            extra_arg_types = tuple(check_node(a, env, sigs) for a in node.target.args)
            arg_types = (val_type,) + extra_arg_types
            arg_nodes = (node.value,) + node.target.args
            return _check_call(node.target.target, arg_types, arg_nodes, env, sigs)
        if isinstance(node.target, str):
            return _check_call(node.target, (val_type,), (node.value,), env, sigs)
        target_type = check_node(node.target, env, sigs)
        if isinstance(target_type, TFn):
            if target_type.params and not is_assignable(val_type, target_type.params[0]):
                raise LumonError("Type error: pipe value type mismatch")
            return target_type.returns
        return TAny()

    if isinstance(node, FunctionCall):
        arg_types = tuple(check_node(a, env, sigs) for a in node.args)
        return _check_call(node.target, arg_types, node.args, env, sigs)

    if isinstance(node, LambdaCall):
        for a in node.args:
            check_node(a, env, sigs)
        return TAny()

    if isinstance(node, Lambda):
        child = env.child()
        for p in node.params:
            child.set(p, TAny())
        body_type = check_node(node.body, child, sigs)
        param_types = tuple(child.get(p) for p in node.params)
        return TFn(param_types, body_type)

    if isinstance(node, Block):
        result: object = TNone()
        for stmt in node.statements:
            result = check_node(stmt, env, sigs)
        return result

    if isinstance(node, ReturnStatement):
        return check_node(node.value, env, sigs)

    if isinstance(node, IfElseExpr):
        check_node(node.condition, env, sigs)
        then_t = check_node(node.then_expr, env, sigs)
        else_t = check_node(node.else_expr, env, sigs)
        if type(then_t) is type(else_t):
            return then_t
        return TAny()

    if isinstance(node, IfStatement):
        check_node(node.condition, env, sigs)
        check_node(node.body, env, sigs)
        if node.else_body is not None:
            check_node(node.else_body, env, sigs)
        return TAny()

    if isinstance(node, MatchExpr):
        check_node(node.subject, env, sigs)
        for arm in node.arms:
            check_node(arm.body, env.child(), sigs)  # type: ignore[union-attr]
        return TAny()

    if isinstance(node, DefineBlock):
        env.register_define(node)
        return TAny()

    if isinstance(node, ImplementBlock):
        define = env.get_define(node.namespace_path)
        if define is not None:
            # Check body return type vs define's declared return type
            impl_env = env.child()
            for param in define.params:  # type: ignore[union-attr]
                if isinstance(param, ParamDef):
                    impl_env.set(param.name, parse_type_expr(param.type_expr))
            body_type = _check_body(node.body, impl_env, sigs)
            declared = parse_type_expr(define.return_type)
            if not isinstance(declared, TAny) and not isinstance(body_type, TAny):
                if not is_assignable(body_type, declared):
                    raise LumonError(
                        f"Type error: implement {node.namespace_path} returns "
                        f"{_type_name(body_type)}, expected {_type_name(declared)}"
                    )
        return TAny()

    if isinstance(node, TestBlock):
        test_env = env.child()
        _check_body(node.body, test_env, sigs)
        return TAny()

    if isinstance(node, AssertStatement):
        check_node(node.expr, env, sigs)
        return TAny()

    if isinstance(node, Program):
        result = TAny()
        for stmt in node.statements:
            result = check_node(stmt, env, sigs)
        return result

    # Everything else (ask, spawn, with, etc.) → permissive
    return TAny()


# ── Helpers ──────────────────────────────────────────────────────────


def _check_body(body: tuple[object, ...], env: TypeEnv, sigs: dict[str, tuple[tuple[object, ...], object]]) -> object:
    """Check a sequence of statements, returning the type of the last / return."""
    result: object = TNone()
    for stmt in body:
        result = check_node(stmt, env, sigs)
    return result


def _check_numeric(left: object, right: object, op: str) -> None:
    for operand in (left, right):
        if isinstance(operand, TAny):
            continue
        if not isinstance(operand, TNumber):
            raise LumonError(f"Type error: operator '{op}' requires number operands")


def _check_addable(left: object, right: object) -> None:
    if isinstance(left, TAny) or isinstance(right, TAny):
        return
    # Both must be same: both number or both text
    if isinstance(left, TNumber) and isinstance(right, TNumber):
        return
    if isinstance(left, TText) and isinstance(right, TText):
        return
    # Union can't be added
    if isinstance(left, TUnion) or isinstance(right, TUnion):
        raise LumonError("Type error: operator '+' requires matching number or text operands")
    raise LumonError("Type error: operator '+' requires matching number or text operands")


def _check_comparable(left: object, right: object, op: str) -> None:
    if isinstance(left, TAny) or isinstance(right, TAny):
        return
    if type(left) is not type(right):
        raise LumonError(
            f"Type error: operator '{op}' requires operands of the same type"
        )


def _check_call(
    name: str,
    arg_types: tuple[object, ...],
    arg_nodes: tuple[object, ...],
    env: TypeEnv,
    sigs: dict[str, tuple[tuple[object, ...], object]],
) -> object:
    """Check a function call against builtin signatures or user defines."""
    # Check builtin signatures
    if name in sigs:
        param_types, return_type = sigs[name]
        # Arity check
        if len(arg_types) != len(param_types):
            raise LumonError(
                f"Type error: {name} expects {len(param_types)} argument(s), "
                f"got {len(arg_types)}"
            )
        # Resolve generics
        substitutions: dict[str, object] = {}
        for actual, expected in zip(arg_types, param_types):
            _bind_type_var(actual, expected, substitutions)

        # Check each arg
        for i, (actual, expected) in enumerate(zip(arg_types, param_types)):
            resolved_expected = _resolve(expected, substitutions)
            # If expected is a function type, check lambda arg
            if isinstance(resolved_expected, TFn) and isinstance(
                arg_nodes[i], Lambda
            ):
                lambda_node: Lambda = arg_nodes[i]  # type: ignore[assignment]
                child = env.child()
                for j, p in enumerate(lambda_node.params):
                    if j < len(resolved_expected.params):
                        child.set(p, resolved_expected.params[j])
                    else:
                        child.set(p, TAny())
                body_type = check_node(lambda_node.body, child, sigs)
                if not isinstance(resolved_expected.returns, TAny) and not isinstance(
                    body_type, TAny
                ):
                    if not is_assignable(body_type, resolved_expected.returns):
                        raise LumonError(
                            f"Type error: lambda returns {_type_name(body_type)}, "
                            f"expected {_type_name(resolved_expected.returns)}"
                        )
                # Bind return type var
                _bind_type_var(body_type, expected if isinstance(expected, TFn) else resolved_expected, substitutions)
                continue
            if isinstance(actual, TAny):
                continue
            if not isinstance(resolved_expected, TAny) and not is_assignable(
                actual, resolved_expected
            ):
                raise LumonError(
                    f"Type error: argument {i + 1} of {name} expects "
                    f"{_type_name(resolved_expected)}, got {_type_name(actual)}"
                )

        return _resolve(return_type, substitutions)

    # User-defined function
    define = env.get_define(name)
    if define is not None:
        return parse_type_expr(define.return_type)

    # Unknown function → permissive
    return TAny()


def _type_name(typ: object) -> str:
    """Human-readable name for a type."""
    if isinstance(typ, TNumber):
        return "number"
    if isinstance(typ, TText):
        return "text"
    if isinstance(typ, TBool):
        return "bool"
    if isinstance(typ, TNone):
        return "none"
    if isinstance(typ, TAny):
        return "any"
    if isinstance(typ, TList):
        return f"list<{_type_name(typ.element)}>"
    if isinstance(typ, TMap):
        return "map"
    if isinstance(typ, TTag):
        if typ.payload:
            return f":{typ.name}({_type_name(typ.payload)})"
        return f":{typ.name}"
    if isinstance(typ, TUnion):
        return " | ".join(_type_name(t) for t in typ.types)
    if isinstance(typ, TFn):
        params = ", ".join(_type_name(p) for p in typ.params)
        return f"fn({params}) -> {_type_name(typ.returns)}"
    if isinstance(typ, TVar):
        return typ.name
    return "unknown"


# ── Entry point ──────────────────────────────────────────────────────


def type_check(
    ast: object,
    *,
    io_backend: object = None,
    git_backend: object = None,
) -> None:
    """Run static type checking on a parsed AST. Raises LumonError on type errors."""
    sigs = dict(BUILTIN_SIGS)
    if io_backend is not None:
        sigs.update(IO_SIGS)
    if git_backend is not None:
        sigs.update(GIT_SIGS)
    env = TypeEnv()
    check_node(ast, env, sigs)
