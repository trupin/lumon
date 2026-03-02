# Claude Code Configuration for Lumon

Drop-in configuration that gives a Claude Code agent access to Lumon and nothing else.

## What's inside

- `settings.json` — Locks the agent to the `lumon` CLI only. No arbitrary shell, no file editing, no Python.
- `CLAUDE.md` — Agent instructions: how to discover, implement, test, and debug using Lumon.

## Setup

Copy these files into your project's `.claude/` directory:

```bash
cp -r cli/claude/ your-project/.claude/
```

Then run Claude Code from your project root. The agent will only be able to use `lumon` commands.

## Prerequisites

`lumon` must be installed and on your PATH:

```bash
pip install lumon
```

## What the agent can do

- `lumon browse` — discover namespaces and function signatures
- `lumon 'implement ...'` — write function implementations
- `lumon 'test ...'` — write and run tests
- `lumon 'return ...'` — execute Lumon code
- `lumon respond '...'` — respond to ask/spawn prompts
- Read `.lumon` files to understand existing code

## What the agent cannot do

- Run shell commands other than `lumon`
- Edit or write files directly
- Use Python, pip, curl, or any other tool
- Access files outside the project root
- Make arbitrary HTTP requests

Safety is enforced at two levels: Claude Code permissions (this config) restrict tool access, and the Lumon interpreter itself enforces filesystem and network boundaries invisibly.
