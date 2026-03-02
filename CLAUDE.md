# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lumon is a minimal, safe, pseudocode-like interpreted language designed to define the cognitive boundary of an AI agent. Safety is achieved by construction — agents can only operate within the primitives the language provides. No sandboxing, no permission prompts.

**Current stage**: Language specification (v0.1 draft) + proof-of-concept validation scripts. The interpreter has not been built yet.

## Repository Structure

- `docs/spec.md` — Full language specification (types, operators, control flow, functions, namespaces, tests, built-ins, execution model, examples)
- `docs/context.md` — Architecture vision, design principles, use cases, technical decisions, comparison to alternatives
- `scripts/ask_poc.py` — POC validating the `ask` coroutine mechanism using Python generators
- `scripts/spawn_poc.py` — POC validating `spawn` + `ask` + `await_all` orchestration

No dependencies beyond Python stdlib (uses generators, not asyncio).

## Architecture

### Two-Layer Design
1. **Interface layer** (`define` blocks) — Typed function signatures with descriptions, browsable by agents
2. **Implementation layer** (`implement` blocks) — Agent-authored code using safe primitives, written at runtime

### Key Language Concepts
- **Immutable bindings only** (`let`) — no mutation, shadowing allowed
- **No loops** — functional iteration via `list.map`, `list.filter`, `list.fold`
- **Pattern matching** — `match` expressions with destructuring
- **Agent coroutines** — `ask` suspends execution for agent judgment, `spawn` delegates to sub-agents
- **Expression-oriented** — everything returns a value
- **Two-layer error model** — recoverable errors use tag returns (`:ok | :error(text)`), interpreter errors (bugs in Lumon code) halt execution with structured JSON

### Execution Model
- Generator-based coroutines (Python `yield`/`.send()`)
- Stateless across sessions — replayed from start by feeding previous responses
- All output is structured JSON (result, error, ask, spawn_batch)
- CLI-based interface (`lumon` command) — no SDK needed

### Discovery Model (Token-Efficient)
```
index.lumon          → Always in agent context (lightweight namespace index)
manifests/<ns>.lumon → Loaded on demand (function signatures)
impl/<ns>.lumon      → Loaded on call (implementations)
```

## Development Methodology

**Test-driven, spec-first.** The spec (`docs/spec.md`) is the source of truth.

1. **Write all tests first** from the spec — every feature must have tests before any implementation begins
2. **All tests fail initially** (red) — this is expected
3. **Implement iteratively** until all tests pass (green)

### Test approach
- **E2E / black-box**: tests invoke the interpreter with Lumon code and assert on JSON output
- **Only mock I/O and network**: `io.*` uses a mock filesystem, `http.*` uses a mock network layer. Everything else (parsing, type checking, execution) runs for real
- **Framework**: `pytest`
- **Invocation**: thin Python API (`interpret(code) -> json`) with injected `io`/`http` backends — black-box from the language's perspective

### Test structure (one file per spec area)
- `test_types.py` — literals, tags, type checking
- `test_bindings.py` — let, shadowing
- `test_operators.py` — arithmetic, comparison, boolean, pipe, nil-coalescing
- `test_control_flow.py` — if/else, match, guards, with/then/else, ask, spawn
- `test_functions.py` — define, implement, lambdas, closures, recursion
- `test_builtins.py` — text.*, list.*, map.*, number.*, type.*
- `test_io.py` — io.read, io.write, io.list_dir (mocked filesystem)
- `test_http.py` — http.get (mocked network, blacklist)
- `test_type_checker.py` — all static type errors
- `test_errors.py` — error model (recoverable vs interpreter)

## Validation Commands

Two slash commands for validating correctness:

- `/test` — runs pytest (`/test` for full suite, `/test tests/test_types.py` for a specific file)
- `/typecheck` — runs pyright (`/typecheck` for the lumon package, `/typecheck lumon/parser.py` for a specific file)

### When to run them

- **After wrapping up a task** — always run both before considering a task done
- **When debugging** — run `/test` with the relevant test file to get failure details
- **Not after every small edit** — only when you need signal, not after each line change

### Definition of done

A task is **not done** unless:
1. It has a test designed for it
2. That test passes
3. No test regressions (all previously passing tests still pass)
4. No pyright errors in modified files

## Git Workflow

- `/commit` — commit current changes (one commit per significant task)
- `/pr` — open a pull request for the current branch (one PR per session)

### Rules

- **Never commit directly to main/master.** Always work on a feature branch.
- **One commit per significant task.** Each commit is a coherent unit of work.
- **One PR per session.** The PR summarizes all commits on the branch.
- **Branch naming**: `feat/...`, `fix/...`, `refactor/...`, etc.

## Tooling

- **Package manager**: Always use `uv` for installing dependencies. Never use `pip`, `pip3`, or `python -m pip`.
  - Add deps to `pyproject.toml`, then run `uv pip install -e ".[dev]"`
  - Or install directly: `uv pip install <package>`
- **Run Python**: `.venv/bin/python`
- **Run pytest**: `.venv/bin/python -m pytest`
- **Run pyright**: `.venv/bin/python -m pyright`

## Planned Implementation

- **Interpreter**: Python first (fast iteration), Rust later (Wasm target)
- **Parser**: `lark`, `pyparsing`, or hand-rolled recursive descent
- **Type system**: Full type checker — catches 100% of type errors before execution (parameterized lists, structural maps, tag exhaustiveness, type inference on locals)
- **Testing**: Built-in `test` blocks with `assert` — tests auto-run on implementation changes

## Design Principles

- Safety by construction over sandboxing
- Code as persistent memory (flat context cost vs. growing prompt cost)
- Self-implementing: agents write their own `implement` blocks
- Self-healing: agents read structured errors and rewrite failing code
- Minimal surface area: only primitives that are provably safe
