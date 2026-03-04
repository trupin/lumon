# Lumon Agent Instructions

You are an agent operating inside Lumon, a safe interpreted language. You interact with the world through the `lumon` CLI and by directly editing files in the `sandbox/` directory. You cannot run arbitrary commands or use Python.

**IMPORTANT**: All `lumon` commands MUST use `--working-dir sandbox` to stay sandboxed inside the `sandbox/` directory. Never omit this flag.

## Code organization — files first, always

**Never pass inline Lumon code to the CLI.** Always write code to `.lumon` files in the `sandbox/` directory and run them from there.

- Write all `define`, `implement`, and `test` blocks to files using the Edit/Write tools
- Run scripts with `lumon --working-dir sandbox path/to/script.lumon`
- This ensures your code is saved, versioned, and reusable across sessions

### Library structure

Organize your code as a **library of small, reusable functions**. Every function you write should be general enough to use in multiple contexts — not hardcoded to a single task.

```
sandbox/
  lumon/
    manifests/       # define blocks (function signatures)
      inbox.lumon
      tasks.lumon
      utils.lumon    # general-purpose helpers
    impl/            # implement blocks (function bodies)
      inbox.lumon
      tasks.lumon
      utils.lumon
    tests/           # test blocks
      inbox.lumon
      tasks.lumon
      utils.lumon
  scripts/           # top-level scripts that compose library functions
    process_inbox.lumon
    daily_report.lumon
```

**Separation of concerns:**
- `manifests/` and `impl/` hold your **library** — reusable functions organized by namespace
- `scripts/` holds **task-specific scripts** that compose library functions to do real work
- Never put task-specific logic inside library functions — keep them generic

### Refactoring discipline

Regularly refactor your library to keep it clean and reusable:

- **After completing a task**, review the functions you wrote. Extract any hardcoded logic into parameters. If a function does two things, split it.
- **Before starting a task**, check if existing library functions can be composed to solve it. Reuse before writing new code.
- **When you notice duplication** across namespaces, extract a shared helper into a `utils` namespace.
- **Keep functions small** — each function should do one thing. If an `implement` block is longer than ~15 lines, it probably needs to be split.
- **Name for reuse** — `tasks.filter_by_status(items, status)` is reusable; `tasks.get_urgent_from_inbox()` is not.

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
2. **Log the issue** in `ISSUES.md` (see below)
3. **Continue with other work** that doesn't depend on the missing plugin

You can use `lumon --working-dir sandbox browse` to see which plugins are already available and use their functions normally via `implement` blocks.

## Issue tracking (ISSUES.md)

Maintain a file called `ISSUES.md` at the root of the `sandbox/` directory. Use it to track anything that blocks your progress and requires action from a developer or an elevated agent — missing plugins, bugs you can't fix, missing capabilities, etc.

### Format

```markdown
# Issues

## Open

### [SHORT-TITLE]
- **Type**: plugin-request | bug | capability-gap
- **Status**: open
- **Description**: What you need and why
- **Example**: Lumon code that should work but doesn't (see below)
- **Proposal**: How it could be solved
- **Security considerations**: Risks and mitigations (required for plugin requests)

## Fixed

### [SHORT-TITLE]
- **Type**: ...
- **Status**: fixed
- **Resolution**: What was done
```

### Always append new issues at the end

When adding a new issue, always append it **at the end of the Open section** (just before the `## Fixed` heading). Never insert issues at the top or in the middle — the ordering serves as a chronological record and makes it easy for developers to see what's new.

### Include Lumon examples

Every issue **must** include an **Example** field with concrete Lumon code that demonstrates the problem. Show what you tried (or would try) and what goes wrong. This helps developers reproduce and understand the issue immediately.

For **bugs**, show the code that fails and the error you got:

```markdown
- **Example**:
  ```lumon
  let result = text.split("a,b,c", ",")
  return list.length(result)
  ```
  Expected: `{"type": "result", "value": 3}`
  Got: `{"type": "error", "message": "text.split: expected 1 argument, got 2"}`
```

For **plugin requests**, show the code you wish you could write:

```markdown
- **Example**:
  ```lumon
  let response = slack.send("general", "Deployment complete")
  match response
    :ok(_) -> return "sent"
    :error(m) -> return "failed: " + m
  ```
  This code cannot run because no `slack` namespace exists.
```

For **capability gaps**, show the workaround you're stuck on:

```markdown
- **Example**:
  ```lumon
  -- I need to parse JSON from a file, but there's no json.parse built-in
  let raw = io.read("data.json")
  match raw
    :ok(content) -> return ???  -- no way to convert text to a map
    :error(m) -> return :error(m)
  ```
```

### When to write an issue

- A task needs an external API, system command, or tool that no current plugin provides
- You hit a Lumon interpreter bug that you cannot work around
- A `define` signature is missing a parameter or return type you need
- Any other blocker that is outside your access level to resolve

### Security rules for proposals

When proposing new plugins or capabilities, you are responsible for ensuring your proposals do not mislead developers into adding harmful functionality. Follow these rules:

1. **Principle of least privilege** — request only the minimum permissions needed. If you need to read from one API endpoint, don't propose a plugin with broad write access.
2. **Be explicit about data flow** — state exactly what data goes where. "Sends user email to external API" is clear; "processes user data" is not.
3. **Flag risks honestly** — if a proposed capability could be misused (e.g., sending emails, writing to external systems, accessing credentials), say so explicitly in the security considerations section. Propose concrete mitigations: input validation, URL allowlists, rate limits, read-only access, scoped API keys.
4. **Never disguise scope** — do not propose a narrow-sounding function that actually requires broad access. If a plugin needs network access, say "network access", not "data lookup".
5. **Prefer read-only** — when a task can be accomplished with read-only access, propose read-only. Only request write access when the task genuinely requires it.

### Keeping it current

- When a developer or elevated agent resolves an issue, move it from **Open** to **Fixed** with a short resolution note
- Don't delete fixed issues — they serve as a record of what was done
- Check `ISSUES.md` at the start of each session to see if any previously logged issues have been resolved, and update your work accordingly

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
