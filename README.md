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
| `lumon deploy <target>` | Deploy Claude Code agent config to a directory |
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
