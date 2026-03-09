# Lumon

> **Status**: Early development — the interpreter is implemented but the language spec and APIs may change without notice. Not suitable for production use.

**A safe, self-implementing language for AI agents.**

Lumon is a minimal interpreted language that defines what an AI agent can and cannot do — not through sandboxing, but through language design. If a primitive doesn't exist in Lumon, the agent cannot conceive of the action. There is nothing to escape from.

## Why Lumon

Production AI systems face three compounding problems:

**Context bloat.** Every tool schema lives in the prompt, on every request. As agents gain capabilities, context grows — and so does cost. There's no way to selectively unload tools without losing them.

**Security by hope.** MCP servers and tool registries are trust decisions. Each tool implementation must be reviewed, sandboxed, or trusted wholesale. Prompt injection can trick an agent into misusing any tool it can reach.

**Maintenance overhead.** Tools are written by humans, registered by humans, updated by humans. Agents can use them but not adapt or extend them. Every new capability requires a development cycle.

Lumon takes a different approach to all three.

## How It Works

Agents write their own capabilities in Lumon at runtime, using only the language's safe primitives. Those implementations persist as code and are reloaded on demand — not kept in context.

```
-- Agent writes this the first time it needs to triage an inbox
implement inbox.triage
  let items = io.read("inbox.json") |> json.parse
  let urgent = items |> list.filter(fn(item) -> item.priority == "high")
  return urgent |> list.map(fn(item) -> item.subject)
```

Next session, that function loads from disk in a handful of tokens. The agent doesn't rewrite it. The LLM isn't involved at runtime — it's just code.

## Key Properties

**Safety by construction.** Lumon's primitives are small, auditable, and safe. Composition of safe primitives produces safe programs — no runtime enforcement needed. The agent can't exfiltrate data via HTTP POST because `http.post` doesn't exist. It can't escape the filesystem because `io.*` is bounded to the working directory. These aren't restrictions bolted on — they're the shape of the language.

**Flat context cost.** The agent keeps only the language spec and a lightweight namespace index in context. Capabilities load on demand when called. An agent with 200 self-authored functions costs the same to run as one with 5. Context cost stays flat as capability grows.

**CLI-native interoperability.** Lumon runs as a standard CLI. Any AI agent with shell access — Claude Code, Cursor, Aider, custom agents — can use it without SDK integration or tool registration. Output is structured JSON. Resuming suspended execution (`ask`/`spawn` coroutines) is one shell command.

```bash
lumon 'return 1 + 2'          # inline execution
lumon path/to/file.lumon      # execute a file
lumon respond '{"answer": 42}'  # resume after agent decision
lumon browse inbox             # discover available functions
```

**Self-implementing agents.** Agents write their own `implement` blocks at runtime. The interface (function signatures + descriptions) is community-maintained and stable. Implementations are agent-authored and environment-specific. New users start with a full interface and zero implementations — the agent builds its toolbox as it works.

**Self-healing.** When an implementation fails, the interpreter returns structured JSON with full context — the function that failed, its inputs, the stack trace. The agent reads the error like a developer reads a traceback and rewrites the implementation. No human triages bugs in agent-authored code.

## Comparison

| | MCP / Tool Use | Lumon |
|:--|:--|:--|
| Capabilities | Pre-defined by developers | Self-authored by agent at runtime |
| Adding new ones | Human writes code, registers tool | Agent writes code in safe language |
| Context cost | Every tool schema in context | Language spec + manifest index only |
| Safety | Trust each tool implementation | Trust the language's primitives |
| Auditability | Check each tool call | Read the agent's source code |
| Persistence | Stateless per session | Code is memory, persists across sessions |
| Discovery | Flat list of tools | Hierarchical, semantic, incremental |

## Install

Requires Python 3.11+.

```bash
# Install as a standalone CLI tool (recommended)
uv tool install .

# Or install into the current environment
uv pip install .
```

## Quick Look

```lua
let names = ["Alice", "Bob", "Carol"]
let greeting = names
  |> list.map(fn(name) -> "Hello, \(name)!")
  |> text.join("\n")

return """
  Welcome to Lumon.

  \(greeting)
  """
```

Key features: immutable bindings (`let`), no loops (use `list.map`/`filter`/`fold`), pattern matching (`match`), pipes (`|>`), tags (`:ok`, `:error("msg")`), triple-quoted strings (`"""..."""`), and agent coroutines (`ask`/`spawn`).

## Usage

```bash
# Inline code
lumon 'return 1 + 2'

# From a file
lumon path/to/file.lumon

# From stdin
echo 'return "hello"' | lumon

# Show the language spec
lumon spec
```

### Subcommands

| Command | Description |
|---------|-------------|
| `lumon <code>` | Execute inline Lumon code |
| `lumon <file.lumon>` | Execute a Lumon file |
| `lumon browse [namespace]` | Show namespace index or a specific manifest |
| `lumon test [namespace]` | Run Lumon test files |
| `lumon respond '<json>'` | Resume suspended execution (after ask/spawn) |
| `lumon respond --file path` | Resume with JSON payload from a file |
| `lumon deploy <target>` | Deploy Claude Code agent config to a directory |
| `lumon schedule add <file>` | Schedule a script to run automatically (macOS) |
| `lumon schedule list` | List all scheduled jobs |
| `lumon schedule edit <id>` | Change a job's schedule |
| `lumon schedule remove <id>` | Remove a scheduled job |
| `lumon schedule logs <id>` | View execution logs for a job |
| `lumon spec` | Print the language specification |

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
.venv/bin/python -m pytest

# Type check
.venv/bin/python -m pyright lumon/
```

## Plugins

Lumon supports a plugin system for extensibility. Plugins are self-contained directories that extend the agent's capabilities with external programs (web APIs, databases, browsers). A `.lumon.json` config controls which plugins are loaded and enforces parameter contracts.

## Documentation

- [Language Specification](docs/spec.md) — full spec (types, operators, control flow, functions, builtins, execution model)
- [Architecture & Context](docs/context.md) — design principles, use cases, technical decisions
