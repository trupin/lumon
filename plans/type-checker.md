# Type Checker Implementation Plan

## Context

18 type_checker tests fail because no static type checking exists. The interpreter pipeline is currently parse → eval with no type validation. The spec requires "all type errors caught statically — none occur at runtime." The type checker must pass all 18 failing tests without regressing the 361 currently passing.

## Approach: Single new module + 2-line integration

### New file: `lumon/type_checker.py` (~500 lines)

**1. Type representation** — frozen dataclasses:
- `TNumber`, `TText`, `TBool`, `TNone`, `TAny` (concrete primitives)
- `TList(element)`, `TMap(fields)`, `TTag(name, payload)` (compound)
- `TUnion(types)`, `TFn(params, returns)`, `TVar(name)` (algebraic)
- `parse_type_expr(expr)` — converts parser dict/string format to internal types

**2. Builtin type signatures** — dict mapping all 46 builtins to `(params, return_type)`:
- Simple: `text.length: fn(text) -> number`, `number.round: fn(number) -> number`
- Generic: `list.map: fn(list<a>, fn(a) -> b) -> list<b>`, `list.head: fn(list<a>) -> a | none`
- IO backends only registered when backends provided (prevents false errors)

**3. Type environment** — `TypeEnv` class with scope chain:
- Tracks `name → LumonType` bindings
- Shared `_defines`/`_implements` registries (like Environment)
- Returns `TAny()` for unknown variables (evaluator handles undefined errors)

**4. Core: `check_node(node, env) -> LumonType`** — recursive AST walker:

| Node | Logic |
|------|-------|
| Literals | Return concrete type (`TNumber`, `TText`, etc.) |
| `ListLiteral` | Infer element types, error if mixed (catches 3 tests) |
| `BinaryOp(-, *, /, %)` | Both sides must be `TNumber` (catches 3 tests) |
| `BinaryOp(<, >, <=, >=)` | Both sides must be same concrete type |
| `BinaryOp(+)` | Must be `num+num` or `text+text` |
| `BinaryOp(and, or, ??)` | Return `TAny` (truthy/falsy semantics) |
| `FunctionCall` to builtin | Check arity + arg types via signatures with generic resolution (catches 8 tests) |
| `FunctionCall` to user fn | Return define's declared return type |
| `ImplementBlock` | Check body return type vs define's declared return type (catches 2 tests) |
| Lambda arg to builtin | Infer lambda body type using expected param types from signature (catches 1 test) |
| Union + arithmetic | `TUnion` not assignable to `TNumber` — catches `list.head(x) + 1` (catches 1 test) |
| Everything else | Return `TAny()` (permissive, no false positives) |

**5. Generic type resolution** — `resolve_type_var(type, substitutions)`:
- When checking `list.map([1,2,3], fn(x) -> "t")`: first arg `TList(TNumber)` binds `a=TNumber`
- Lambda checked with `x: TNumber`, body infers `TText`, binds `b=TText`
- Return type `TList(TVar("b"))` resolves to `TList(TText)`

**6. Key helper: `is_assignable(actual, expected) -> bool`:**
- `TAny`/`TVar` → always True (permissive)
- `TUnion` as actual → False (union can't satisfy concrete requirement)
- Same concrete types → True
- `TList(a)` to `TList(b)` → recursive check
- This is the mechanism that catches union-type-not-handled errors

### Modified file: `lumon/interpreter.py` (2 lines added)

```python
from lumon.type_checker import type_check
# Insert between parse() and eval_node():
type_check(ast, io_backend=io_backend, http_backend=http_backend)
```

## Regression safety

- Unknown variables → `TAny()` (evaluator catches undefined)
- Unknown functions → `TAny()` (evaluator catches undefined)
- `and`/`or` → `TAny()` (truthy/falsy works on all types)
- IO builtins without backend → not registered, returns `TAny()`
- `FieldAccess` on namespace refs → `TAny()` (evaluator handles)
- Complex expressions (ask, spawn, with, match result) → `TAny()`
- Empty lists → `TList(TAny())`

## Verification

1. `pytest tests/test_type_checker.py` — all 18 must pass
2. `pytest` full suite — 361+ must still pass (target 379/380)
3. `pyright lumon/` — 0 errors
