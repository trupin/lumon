# Lumon Agent Instructions

You are an agent operating inside Lumon, a safe interpreted language. You interact with the world through the `lumon` CLI and by directly editing files in the `sandbox/` directory. You cannot run arbitrary commands or use Python.

**IMPORTANT**: All `lumon` commands MUST use `--working-dir sandbox` to stay sandboxed inside the `sandbox/` directory. Never omit this flag.

## How to read the language spec

```bash
lumon spec
```

This prints the full Lumon language specification: types, operators, control flow, built-ins, error model, and execution semantics. Read it before writing any code.

## How to discover capabilities

```bash
# List all namespaces (always start here)
lumon --working-dir sandbox browse

# Show function signatures for a namespace
lumon --working-dir sandbox browse inbox
lumon --working-dir sandbox browse io
```

Read the signatures carefully — they include parameter types, descriptions, and return types. This is your API reference.

## How to implement functions

Write `implement` blocks by passing Lumon code to the CLI. The interpreter saves them to disk automatically.

```bash
lumon --working-dir sandbox 'implement inbox.read
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
lumon --working-dir sandbox 'return list.sort([3, 1, 2])'

# Call a function you implemented
lumon --working-dir sandbox 'return inbox.read("INBOX.md")'

# From a file
lumon --working-dir sandbox impl/inbox.lumon

# From stdin
echo 'return 42' | lumon --working-dir sandbox
```

All output is structured JSON:

```json
{"type": "result", "value": [1, 2, 3]}
```

## How to test

```bash
# Run all tests for a namespace
lumon --working-dir sandbox test inbox

# Run all tests
lumon --working-dir sandbox test
```

Write `test` blocks the same way you write `implement` blocks:

```bash
lumon --working-dir sandbox 'test inbox.read
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
lumon --working-dir sandbox respond '{"action": "process", "item": "Pay bill"}'
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

## File editing

You can directly read and edit files inside the `sandbox/` directory using the Edit and Read tools. This is useful for:
- Creating and editing `.lumon` source files, manifests, and test files
- Setting up project structure (`sandbox/lumon/index.lumon`, `sandbox/lumon/manifests/`, etc.)
- Writing data files that Lumon code reads via `io.read`

All file operations are restricted to `sandbox/` — edits outside that directory will be blocked.

## Plugins

Plugins extend Lumon with external capabilities (APIs, scripts, system tools). They are set up by a separate agent with elevated access — **you cannot create or modify plugins yourself**.

If a task requires capabilities beyond what the current namespaces provide (e.g., calling an external API, running a shell script, accessing a database), do the following:

1. **Stop** — do not attempt to create plugin directories, write manifest files, or edit `.lumon.json`
2. **Report back** that a plugin would be required to complete the task
3. **Describe what the plugin would need**: the namespace, function signatures, what each function should do, and what external system it would talk to
4. **Continue with other work** that doesn't depend on the missing plugin

You can use `lumon --working-dir sandbox browse` to see which plugins are already available and use their functions normally via `implement` blocks.

## What you cannot do

- Run arbitrary shell commands (only `lumon --working-dir sandbox` is available)
- Edit or create files outside the `sandbox/` directory
- Access Python, pip, or any other tooling
- Read files outside the current project directory
- Make HTTP POST requests or send authenticated requests
- Create or modify plugins (only a separate agent with elevated access can do this)

These restrictions are by design. Everything you need is available through Lumon primitives and direct file editing in `sandbox/`.

## CLI quick reference

| Command | What it does |
| :--- | :--- |
| `lumon spec` | Print the full language specification |
| `lumon --working-dir sandbox 'code'` | Run inline Lumon code |
| `lumon --working-dir sandbox file.lumon` | Run a `.lumon` file |
| `echo 'code' \| lumon --working-dir sandbox` | Run code from stdin |
| `lumon --working-dir sandbox browse` | List all namespaces |
| `lumon --working-dir sandbox browse <ns>` | Show function signatures for a namespace |
| `lumon --working-dir sandbox test` | Run all test files |
| `lumon --working-dir sandbox test <ns>` | Run tests for a specific namespace |
| `lumon --working-dir sandbox respond '<json>'` | Resume a suspended `ask` or `spawn` |

## Language quick reference

- **Bindings**: `let x = 42` (immutable, shadowing allowed)
- **Tags**: `:ok`, `:error("msg")` (like enums with payloads)
- **Match**: `match expr` with patterns, guards, destructuring
- **Pipes**: `items |> list.sort |> list.take(3)`
- **Lambdas**: `fn(x) -> x * 2` (multi-line with `let` bindings works everywhere, including as function arguments)
- **No loops**: use `list.map`, `list.filter`, `list.fold`
- **Nil-coalescing**: `value ?? "default"`
- **Types**: `text`, `number`, `bool`, `list<T>`, `map`, `tag`, `none`
