# Lumon

A minimal, safe, pseudocode-like interpreted language that defines the cognitive boundary of an AI agent.

Safety is achieved by construction — agents can only operate within the primitives the language provides. No sandboxing, no permission prompts.

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

### Agent Coroutines

The defining feature: `ask` suspends execution for agent judgment, `spawn` delegates to sub-agents. Code handles the mechanical work, agents handle the reasoning.

```lua
-- Two sub-agents debate, then the main agent picks a winner

let topic = "Tabs vs spaces"

let for_position = spawn
  "Argue FOR the following position. Be concise and persuasive."
  context: topic
  expects: {argument: text}

let against_position = spawn
  "Argue AGAINST the following position. Be concise and persuasive."
  context: topic
  expects: {argument: text}

let verdict = ask
  "Two agents debated this topic. Read both arguments and pick a winner."
  context: {
    topic: topic,
    for: for_position.argument,
    against: against_position.argument
  }
  expects: {winner: text, reasoning: text}

return verdict
```

Running this from the CLI:

```bash
$ lumon debate.lumon
# {"type":"spawn_batch","spawns":[...], "session":"a3f2e1b9", ...}

# The orchestrator runs two sub-agents and writes their responses:
$ echo '{"argument":"Tabs are..."}' > .lumon_comm/a3f2e1b9/spawn_0_response.json
$ echo '{"argument":"Spaces are..."}' > .lumon_comm/a3f2e1b9/spawn_1_response.json
$ lumon respond
# {"type":"ask","prompt":"Two agents debated...","session":"a3f2e1b9", ...}

# The main agent reads both arguments, makes a judgment call:
$ echo '{"winner":"spaces","reasoning":"..."}' > .lumon_comm/a3f2e1b9/ask_response.json
$ lumon respond
# {"type":"result","value":{"winner":"spaces","reasoning":"..."}}
```

The pattern: **code** structures the workflow, **spawn** farms out independent reasoning in parallel, **ask** brings results to the main agent for judgment. The script suspends and resumes automatically — the agent just writes JSON to files and calls `lumon respond`.

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
| `lumon respond [session]` | Resume suspended execution (after ask/spawn) |
| `lumon respond --clear` | Discard a pending session |
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
