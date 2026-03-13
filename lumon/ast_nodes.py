"""Frozen dataclass AST node definitions for the Lumon language."""

from __future__ import annotations

from dataclasses import dataclass


# --- Literals ---

@dataclass(frozen=True)
class NumberLiteral:
    value: int | float


@dataclass(frozen=True)
class TextLiteral:
    value: str


@dataclass(frozen=True)
class InterpolatedText:
    parts: tuple[object, ...]  # alternating str and expression nodes


@dataclass(frozen=True)
class BoolLiteral:
    value: bool


@dataclass(frozen=True)
class NoneLiteral:
    pass


@dataclass(frozen=True)
class ListLiteral:
    elements: tuple[object, ...]


@dataclass(frozen=True)
class MapLiteral:
    entries: tuple[object, ...]  # MapEntry or SpreadEntry


@dataclass(frozen=True)
class MapEntry:
    key: str
    value: object


@dataclass(frozen=True)
class SpreadEntry:
    expr: object


@dataclass(frozen=True)
class TagLiteral:
    name: str
    payload: object | None = None


# --- Bindings ---

@dataclass(frozen=True)
class LetBinding:
    name: str
    value: object


# --- Variables and access ---

@dataclass(frozen=True)
class VarRef:
    name: str


@dataclass(frozen=True)
class FieldAccess:
    obj: object
    field: str


@dataclass(frozen=True)
class IndexAccess:
    obj: object
    index: object


# --- Operators ---

@dataclass(frozen=True)
class BinaryOp:
    op: str
    left: object
    right: object


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: object


@dataclass(frozen=True)
class PipeOp:
    value: object
    target: object


# --- Function definitions ---

@dataclass(frozen=True)
class DefineBlock:
    namespace_path: str
    description: str
    params: tuple[object, ...]
    return_type: object | None
    return_description: str


@dataclass(frozen=True)
class ParamDef:
    name: str
    type_expr: object
    description: str
    default: object | None = None


@dataclass(frozen=True)
class ImplementBlock:
    namespace_path: str
    body: tuple[object, ...]


# --- Function calls ---

@dataclass(frozen=True)
class FunctionCall:
    target: str
    args: tuple[object, ...]


@dataclass(frozen=True)
class LambdaCall:
    target: object
    args: tuple[object, ...]


# --- Lambda ---

@dataclass(frozen=True)
class Lambda:
    params: tuple[str, ...]
    body: object


# --- Block ---

@dataclass(frozen=True)
class Block:
    statements: tuple[object, ...]


# --- Control flow ---

@dataclass(frozen=True)
class IfElseExpr:
    condition: object
    then_expr: object
    else_expr: object


@dataclass(frozen=True)
class IfStatement:
    condition: object
    body: object
    else_body: object | None = None


@dataclass(frozen=True)
class MatchExpr:
    subject: object
    arms: tuple[object, ...]


@dataclass(frozen=True)
class MatchArm:
    pattern: object
    guard: object | None
    body: object


@dataclass(frozen=True)
class WithExpr:
    bindings: tuple[tuple[str, object], ...]
    then_body: object
    else_body: object


# --- Patterns ---

@dataclass(frozen=True)
class LiteralPattern:
    value: object


@dataclass(frozen=True)
class BindPattern:
    name: str


@dataclass(frozen=True)
class WildcardPattern:
    pass


@dataclass(frozen=True)
class TagPattern:
    name: str
    payload_pattern: object | None = None


@dataclass(frozen=True)
class MapPattern:
    entries: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class ListPattern:
    elements: tuple[object, ...]
    rest_name: str | None = None


# --- Return ---

@dataclass(frozen=True)
class ReturnStatement:
    value: object


# --- Coroutines ---

@dataclass(frozen=True)
class AskExpr:
    prompt: object
    context: object | None = None
    expects: object | None = None


@dataclass(frozen=True)
class SpawnExpr:
    tasks: object  # expression evaluating to a list of maps


# --- Testing ---

@dataclass(frozen=True)
class TestBlock:
    name: str
    body: tuple[object, ...]


@dataclass(frozen=True)
class AssertStatement:
    expr: object


# --- Program ---

@dataclass(frozen=True)
class Program:
    statements: tuple[object, ...]
