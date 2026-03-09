---
name: workflow
description: How to discover capabilities, implement functions, run code, test, and respond to ask/spawn in Lumon. Reference this when working through any Lumon task.
---

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

Write `define` blocks to manifest files and `implement` blocks to impl files using the Edit/Write tools, then run them to register:

**Step 1** — Write the signature to `sandbox/lumon/manifests/inbox.lumon`:
```
define inbox.read
  "Extract list items from a markdown file"
  takes:
    path: text "Path to the markdown file"
  returns: :ok(list<text>) | :error(text) "The list items or an error"
```

**Step 2** — Write the implementation to `sandbox/lumon/impl/inbox.lumon`:
```
implement inbox.read
  let result = io.read(path)
  match result
    :error(m) -> return :error(m)
    :ok(content) ->
      let items = content
        |> text.split("\n")
        |> list.filter(fn(l) -> text.starts_with(l, "- "))
        |> list.map(fn(l) -> text.slice(l, 2, text.length(l)))
      return :ok(items)
```

**Step 3** — Use the function from a script file (e.g., `sandbox/scripts/process.lumon`):
```
let result = inbox.read("INBOX.md")
match result
  :ok(items) -> return items
  :error(m) -> return "failed: " + m
```

**Step 4** — Run the script:
```bash
lumon --working-dir sandbox scripts/process.lumon
```

## How to run code

Always write code to a `.lumon` file first, then run it:

```bash
# Run a script file
lumon --working-dir sandbox scripts/my_task.lumon

# Run a test file
lumon --working-dir sandbox test inbox
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

When execution suspends for agent judgment, the output includes a `session` ID and `response_file` paths:

```json
{"type": "ask", "session": "a3f2e1b9", "prompt": "Which item first?\n\nContext data: .lumon_comm/a3f2e1b9/ask_context.json", "expects": {"action": "text"}, "response_file": ".lumon_comm/a3f2e1b9/ask_response.json"}
```

Write your response JSON to the `response_file` path, then resume:

```bash
# 1. Read context from the context file if present
# 2. Write the JSON response to the response_file path from the output
echo '{"action": "process", "item": "Pay bill"}' > .lumon_comm/a3f2e1b9/ask_response.json
# 3. Resume execution
lumon --working-dir sandbox respond
```

For spawn batches, each spawn has its own `response_file` (e.g. `spawn_0_response.json`). Write all responses, then run `lumon respond` once.

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
