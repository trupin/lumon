---
description: General Python coding guidelines for this project. Enforced automatically — Claude should follow these when writing any Python code.
---

Follow these Python guidelines when writing or modifying Python code in this project:

## Imports

- **All imports must be at the top of the file**, after the module docstring and `from __future__` imports. Never use inline/local imports unless there is a circular dependency that cannot be resolved otherwise.
- Group imports in this order, separated by blank lines:
  1. Standard library (`os`, `json`, `subprocess`, etc.)
  2. Third-party packages (`pytest`, `lark`, etc.)
  3. Local project imports (`from lumon.errors import LumonError`, etc.)
- Within each group, sort alphabetically.
- Use `from __future__ import annotations` as the first import in every module (already the convention in this codebase).

## Style

- Follow PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- Use type annotations on all function signatures. Use `object` as the Lumon value type (not `Any`).
- Prefer `isinstance()` checks and `match`/`case` for type dispatch — no `type()` comparisons.
- Use f-strings for string formatting, not `.format()` or `%`.

## Error handling

- Use `LumonError` for all user-facing interpreter errors — never raw `Exception` or `ValueError`.
- Don't catch broad exceptions (`except Exception`) unless re-raising as `LumonError`.
- Use `assert` only for internal invariants that indicate bugs, never for input validation.

## Testing

- Use `pytest` fixtures and parametrize where appropriate.
- Use `tmp_path` fixture for temporary directories — never bare `tempfile.mkdtemp()`.
- Test through the public `interpret()` API (black-box) — don't test internal functions directly unless they have no public path.

## Dependencies

- Use `uv` for all package management. Never `pip`.
- Only standard library for the interpreter core. Third-party deps (`lark`) are declared in `pyproject.toml`.
