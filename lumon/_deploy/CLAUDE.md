# Lumon Agent Instructions

You are an agent operating inside Lumon, a safe interpreted language. You can only interact with the world through the `lumon` CLI. You cannot run arbitrary commands, edit files directly, or use Python.

## How to read the language spec

```bash
lumon spec
```

This prints the full Lumon language specification: types, operators, control flow, built-ins, error model, and execution semantics. Read it before writing any code.

## How to discover capabilities

```bash
# List all namespaces (always start here)
lumon browse

# Show function signatures for a namespace
lumon browse inbox
lumon browse io
```

Read the signatures carefully — they include parameter types, descriptions, and return types. This is your API reference.

## How to implement functions

Write `implement` blocks by passing Lumon code to the CLI. The interpreter saves them to disk automatically.

```bash
lumon 'implement inbox.read
  let result = io.read(path)
  match result
    :error(m) -> return :error(m)
    :ok(content) ->
      let items = content
        |> text.split("\n")
        |> list.filter(fn(l) -> text.starts_with(l, "- "))
        |> list.map(fn(l) -> text.slice(l, 2, text.length(l)))
      return :ok(items)
'
```

## How to run code

```bash
# Inline expression
lumon 'return list.sort([3, 1, 2])'

# Call a function you implemented
lumon 'return inbox.read("INBOX.md")'

# From a file
lumon impl/inbox.lumon

# From stdin
echo 'return 42' | lumon
```

All output is structured JSON:

```json
{"type": "result", "value": [1, 2, 3]}
```

## How to test

```bash
# Run all tests for a namespace
lumon test inbox

# Run all tests
lumon test
```

Write `test` blocks the same way you write `implement` blocks:

```bash
lumon 'test inbox.read
  let result = inbox.read("test/inbox.md")
  match result
    :ok(items) -> assert list.length(items) == 2
    :error(_) -> assert false
'
```

## How to respond to ask/spawn

When execution suspends for agent judgment, the output will be:

```json
{"type": "ask", "prompt": "Which item first?", "context": [...], "expects": {"action": "text"}}
```

Respond with:

```bash
lumon respond '{"action": "process", "item": "Pay bill"}'
```

## Error handling

**Recoverable errors** — functions return `:ok(value)` or `:error(message)`. Handle them with `match`:

```
match io.read("file.md")
  :ok(content) -> return content
  :error(m) -> return "failed: " + m
```

**Interpreter errors** — bugs in your code. The output includes a structured error:

```json
{"type": "error", "function": "inbox.read", "trace": ["inbox.read"], "message": "Undefined variable: raw"}
```

Read the error, fix your implementation, and try again.

## What you cannot do

- Run arbitrary shell commands (only `lumon` is available)
- Edit files directly (use `lumon 'implement ...'` or `lumon 'test ...'` instead)
- Access Python, pip, or any other tooling
- Access files outside the project root (the interpreter enforces this invisibly)
- Make HTTP POST requests or send authenticated requests

These restrictions are by design. Everything you need is available through Lumon primitives.

## CLI quick reference

| Command | What it does |
| :--- | :--- |
| `lumon spec` | Print the full language specification |
| `lumon 'code'` | Run inline Lumon code |
| `lumon file.lumon` | Run a `.lumon` file |
| `echo 'code' \| lumon` | Run code from stdin |
| `lumon browse` | List all namespaces (`lumon/index.lumon`) |
| `lumon browse <ns>` | Show function signatures for a namespace |
| `lumon test` | Run all test files in `lumon/tests/` |
| `lumon test <ns>` | Run tests for a specific namespace |
| `lumon respond '<json>'` | Resume a suspended `ask` or `spawn` |
| `lumon deploy <dir>` | Copy this agent config into `<dir>/.claude/` |

## Language quick reference

- **Bindings**: `let x = 42` (immutable, shadowing allowed)
- **Tags**: `:ok`, `:error("msg")` (like enums with payloads)
- **Match**: `match expr` with patterns, guards, destructuring
- **Pipes**: `items |> list.sort |> list.take(3)`
- **Lambdas**: `fn(x) -> x * 2`
- **No loops**: use `list.map`, `list.filter`, `list.fold`
- **Nil-coalescing**: `value ?? "default"`
- **Types**: `text`, `number`, `bool`, `list<T>`, `map`, `tag`, `none`
