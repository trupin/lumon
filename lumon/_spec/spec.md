# Lumon Language Specification

> Draft v0.1 — A minimal, safe, pseudocode-like interpreted language that defines the cognitive boundary of an AI agent.

---

## 1. Types

Seven primitive types. No custom types.

| Type | Description | Literal examples |
| :---- | :---- | :---- |
| `text` | String of characters | `"hello"`, `"value is \(x)"`, `"""multiline"""` |
| `number` | Integer or float (undifferentiated) | `42`, `3.14`, `-1` |
| `bool` | Boolean | `true`, `false` |
| `list<T>` | Ordered collection (homogeneous) | `[1, 2, 3]`, `["a", "b"]` |
| `map` | Key-value pairs (keys are text) | `{name: "Theo", age: 30}` |
| `tag` | Named label with optional payload | `:ok`, `:error("msg")` |
| `none` | Absence of value | `none` |

Escape sequences in text: `\\` (backslash), `\"` (quote), `\n` (newline), `\t` (tab), `\(expr)` (interpolation).

### Multiline Strings

Triple-quoted strings (`"""..."""`) preserve literal newlines and support the same escape sequences and `\(expr)` interpolation as single-line strings. Internal `"` and `""` are allowed; only `"""` closes the string.

**Dedent rules:**
1. If the first line (after opening `"""`) is blank, strip it.
2. If the last line (before closing `"""`) is whitespace-only, strip it and use its indent as the common indent reference.
3. Otherwise, compute minimum indent of non-empty lines.
4. Strip that common indent from all lines.

```
let msg = """
    Hello,
    World!
    """
-- msg == "Hello,\nWorld!"
```

Empty triple-quoted strings (`""""""`) produce an empty string. Comments (`--`) inside triple-quoted strings are preserved as literal text.

Triple-quoted strings can be used anywhere a regular string is valid: expressions, match patterns, ask/spawn prompts, and define descriptions.

### Tags

Tags are named labels prefixed with `:`. They can carry an optional payload of any type.

```
:ok
:error("file not found")
:pending({retries: 3})
```

No declaration needed — any `:name` is a valid tag. Tags are values like any other: they can be stored in bindings, passed to functions, put in lists.

```
let status = :ok
let result = :error("timeout")
let colors = [:red, :green, :blue]
```

Tags are used in `define` signatures to describe the set of possible return values:

```
define io.write
  "Write content to a file"
  takes:
    path: text "The file to write to"
    content: text "The content to write"
  returns: :ok | :error(text) "Success or error with message"
```

The `|` in the return type declares which tags the function may return. The type checker uses this for exhaustiveness checking (see below).

### Parameterized lists

Lists are parameterized by element type. All elements must be the same type.

```
list<text>                  -- list of strings
list<number>                -- list of numbers
list<{name: text}>          -- list of structural maps
```

The checker infers element types from literals: `[1, 2, 3]` is `list<number>`. Mixed-type literals like `[1, "two"]` are type errors.

### Map types

Two flavors, same underlying data structure:

**Structural maps** — known fields with known types. Created via map literals, accessed with `.field` and pattern matching.

```
{name: text, age: number}            -- type signature
let user = {name: "Theo", age: 30}   -- literal
let n = user.name                    -- n is text
```

Map literal keys are bare identifiers interpreted as text. `{name: "Theo"}` means key `"name"`, not the variable `name`.

Spread syntax creates a new structural map with added or updated fields:

```
let extended = {...user, email: "theo@example.com"}
-- extended: {name: text, age: number, email: text}
```

**Uniform maps** — dynamic keys with uniform value type. Created via `map.set`, accessed with `map.get`/`map.set`.

```
map<number>                  -- type signature (text keys, number values)
let scores = map.set(map.set({}, "math", 95), "english", 88)
let s = map.get(scores, "math")   -- s is number | none
```

The `map.*` built-in functions operate on uniform maps. Structural maps use `.field` access, pattern matching, and spread.

### Type unions

Express alternatives in signatures. Used for tag results and optional values.

```
:ok(text) | :error(text)          -- tagged result
text | none                       -- optional text
```

### Type variables

Built-in signatures use lowercase letters as type variables to express generic operations. The checker infers concrete types at each call site.

```
list.head(items: list<a>) -> a | none
list.map(items: list<a>, f: fn(a) -> b) -> list<b>
```

### Function types

Express the type of a lambda or function reference.

```
fn(text) -> number                -- takes text, returns number
fn(a, b) -> a                    -- generic function
```

Used in built-in signatures for higher-order functions like `list.map` and `list.filter`.

### Truthy / falsy

- Falsy: `false`, `none`, `0`, `""`, `[]`, `{}`
- Everything else is truthy

---

## 2. Bindings

All bindings are **immutable**. `let` creates a new binding. Reusing a name **shadows** the previous binding.

```
let x = 10
let x = x + 1   -- shadows, does not mutate. Old x is gone.
let name = "Lumon"
let items = [1, 2, 3]
```

Every binding requires the `let` keyword. No `var`, `const`, or `mut` — there is only `let`, and it is always immutable.

### Namespaces and variables don't collide

Variables and namespaces live in separate scopes. A variable named `text` does not shadow the `text` namespace — `text.split` still resolves to the namespace function. The interpreter distinguishes them at parse time since namespaces are known and fixed.

---

## 3. Operators

### Arithmetic

| Operator | Meaning |
| :---- | :---- |
| `+` | Add (numbers) or concatenate (text) |
| `-` | Subtract |
| `*` | Multiply |
| `/` | Divide (division by zero is an interpreter error) |
| `%` | Modulo |

### Comparison

| Operator | Meaning |
| :---- | :---- |
| `==` | Equal |
| `!=` | Not equal |
| `<` | Less than |
| `>` | Greater than |
| `<=` | Less than or equal |
| `>=` | Greater than or equal |

### Boolean

| Operator | Meaning |
| :---- | :---- |
| `and` | Logical and |
| `or` | Logical or |
| `not` | Logical not (prefix) |
| `??` | Nil-coalescing — returns left side if not none, else right side |

### Pipe

| Operator | Meaning |
| :---- | :---- |
| `\|>` | Pipe — passes left-hand value as first argument to right-hand function |

The pipe operator enables readable left-to-right data transformation chains:

```
let result = items
  |> list.flat_map(fn(i) -> i.tags)
  |> list.deduplicate
  |> list.sort_by(fn(t) -> t.count)
  |> list.take(10)
```

When the right-hand function takes a single argument, parentheses are optional (`list.deduplicate`). When it takes additional arguments, the piped value is inserted as the first argument (`list.take(10)` becomes `list.take(items, 10)`).

The pipe always inserts into the first position. To pipe into a different argument, wrap in a lambda:

```
let replaced = old_text |> fn(t) -> text.replace(template, "{name}", t)
```

### Access

| Operator | Meaning |
| :---- | :---- |
| `.` | Namespace access (`file.read`) and map field access (`person.name`) |
| `[i]` | List index access (`items[0]`) |

---

## 4. Control Flow

### if / else

Expression-oriented — returns a value. Two forms: block and inline.

**Block form** (multi-line):

```
let status = if count > 0
  "has items"
else
  "empty"
```

**Inline form** (single-line):

```
let status = if count > 0 "has items" else "empty"
```

`else` is required when used as an expression. When used as a statement (return value ignored), `else` is optional.

```
if debug
  log("verbose mode")
```

No `else if` — use `match` for multi-branch logic.

### match

Pattern matching with destructuring. Expression-oriented.

```
match result
  {status: "ok", data: d} -> process(d)
  {status: "error", msg: m} -> log(m)
  none -> fallback()
```

Arms can be a single expression or an indented block. In a block, the last expression is the arm's value.

```
match io.read("config.md")
  :error(_) -> :error("no config")
  :ok(raw) ->
    let parsed = parse(raw)
    let valid = validate(parsed)
    :ok(valid)
```

Patterns can match:
- **Literals**: `"ok"`, `42`, `true`, `none`
- **Bindings**: `x` (matches anything, binds the value to `x`)
- **Maps**: `{key: pattern, ...}` (matches maps with those keys)
- **Lists**: `[first, second, ...rest]` (destructure with optional rest)
- **Tags**: `:ok`, `:error(m)` (matches tag name, optionally destructures payload)
- **Wildcard**: `_` (matches anything, discards the value)
- **Guards**: `pattern if condition` (pattern matches first, then condition is checked)

Match is exhaustive — the interpreter warns if cases are missing. Use `_` as a catch-all.

### Exhaustiveness checking

When the matched value has a known tag set (from a `define` signature or inferred from the implementation), the interpreter checks that all tags are covered.

```
define io.write
  ...
  returns: :ok | :error(text)

implement inbox.save
  let result = io.write("inbox.md", content)
  match result
    :ok -> return "saved"
    -- interpreter warns: missing case :error(text)
```

The interpreter infers tag sets by tracing how values flow through the program:
1. **From `define` signatures** — `returns: :ok | :error(text)` declares the set explicitly
2. **From implementation** — if a function returns `:ok` and `:error(m)` in different branches, the interpreter infers the set `{:ok, :error}`
3. **Through bindings** — `let r = io.write(...)` inherits the tag set of `io.write`'s return type

When a `match` expression handles a value with a known tag set, the interpreter warns if any tag is unhandled and no wildcard (`_`) is present. This is a warning, not an error — the agent can choose to add a catch-all.

```
match code
  200 -> "ok"
  404 -> "not found"
  _ -> "unknown: " + text.from(code)
```

Guards add a boolean condition to a pattern. The pattern must match first, then the guard is evaluated. If the guard is false, the next arm is tried.

```
match item
  x if text.contains(x, "#urgent") -> "urgent"
  x if text.contains(x, "#errand") -> "errand"
  _ -> "uncategorized"
```

### with / then / else

Chain fallible operations. Each step feeds the next. If any step produces `none` or `:error(payload)`, execution jumps to `else`. If a step produces `:ok(payload)`, the payload is automatically unwrapped before binding. Any other value is bound as-is. Expression-oriented — returns the `then` value on success, the `else` value on failure.

```
let content = with
  raw = io.read(path)
  parsed = parse(raw)
  summary = extract_summary(parsed)
then
  summary
else
  "Could not load content"
```

Each binding in the `with` block is checked before proceeding:
- `none` → bail to `else`
- `:error(payload)` → bail to `else`
- `:ok(payload)` → unwrap and bind the payload
- Any other value → bind as-is

No nesting required for chained failure handling.

**Note:** If a step returns a legitimate `none` (e.g., `list.head` on an empty list), the chain will bail. Use `??` to provide a default before the value enters the chain:

```
let context = with
  items = map.get(data, "entries") ?? []
  first = list.head(items) ?? {title: "none"}
  title = first.title
then
  title
else
  "No title found"
```

### ?? (nil-coalescing)

Provides a default value when an expression is `none`.

```
let items = map.get(data, "items") ?? []
let name = user.display_name ?? "Anonymous"
```

Equivalent to `match expr` / `none -> default` / `val -> val`, but much more compact.

### ask (agent coroutine)

Suspends execution, hands data to the agent for a judgment call, and resumes with the agent's response. This is the boundary between deterministic code and LLM reasoning.

```
let decision = ask
  "Which of these should I handle first?"
  context: urgent
  expects: {action: text, item: text}
```

Components:
- **Prompt**: a text string describing what the agent should decide
- **context**: data the agent needs to make the decision (any Lumon value)
- **expects**: the shape of the response as a type signature. The interpreter validates the agent's response against this and re-prompts on mismatch.

The interpreter auto-generates format instructions from `expects` — the function author doesn't write serialization logic. The interpreter handles translation between Lumon types and the agent's response format.

**Multiple exchanges in one function:**

```
implement report.build
  let data = io.read("metrics.md") |> parse_metrics

  let focus = ask
    "Here are this week's metrics. What should the report focus on?"
    context: data
    expects: {topics: list, tone: text}

  let draft = format_report(data, focus)

  let final = ask
    "Here's the draft report. Any changes?"
    context: draft
    expects: text

  io.write("report.md", final)
  return {status: "ok", path: "report.md"}
```

A single function orchestrates a multi-turn conversation between code and agent. Code handles the mechanical work (read, parse, format), the agent provides judgment (what to focus on, review the draft).

When execution hits an `ask`, it suspends and prints a JSON envelope to stdout with the prompt, context file path, expected response shape, and a response file path. The agent writes its answer to the response file and runs `lumon respond` to resume. Execution continues from exactly where it stopped — the response is bound to the variable and the rest of the function runs.

Multiple `ask`s in one function work naturally — each one suspends, waits for a response, and resumes in turn.

### spawn (sub-agent delegation)

Delegates reasoning tasks to sub-agents. Unlike `ask` (which the main agent answers directly), `spawn` tells the orchestrator to create sub-agents. Spawn takes a list of task maps and blocks until all responses arrive, returning a list of results.

```
let [analysis] = spawn [{
  prompt: "Analyze this article for potential bias",
  context: article_text
}]
```

Multiple sub-agents in parallel:

```
let [bias, tone] = spawn [
  {prompt: "check bias", context: article1},
  {prompt: "check tone", context: article2}
]
```

With forked context (sub-agent inherits conversation history):

```
let [analysis] = spawn [{
  prompt: "Given our earlier discussion, analyze this article",
  context: article_text,
  fork: true
}]
```

Each task map has these keys:
- **prompt** (required): the task for the sub-agent
- **context** (optional): data the sub-agent needs (any Lumon value)
- **fork** (optional, default `false`): if `true`, sub-agent inherits the main agent's conversation history
- **expects** (optional): response shape hint

Spawn always returns a **list** of responses, one per task map entry.

**`ask` vs `spawn`:**

| | `ask` | `spawn` |
| :---- | :---- | :---- |
| Who responds | The main agent directly | Sub-agents spawned by the main agent |
| Context | Main agent's full conversation | Fresh (default) or forked |
| Use case | Judgment calls in a workflow | Independent reasoning tasks |
| Returns | Single value | List of values |

---

## 5. Functions

### Interface (define)

Declares a function's contract — typed, described, browsable.

```
define file.read
  "Read the contents of a file"
  takes:
    path: text "The file to read"
    encoding: text "Character encoding" = "utf-8"
  returns: :ok(text) | :error(text) "The file contents, or error"
```

Components:
- **Namespace path**: `namespace.function_name` (dot-separated)
- **Description**: first-class string, not a comment
- **takes**: named parameters with `name: type "description"` and optional `= default`
- **returns**: `type "description"` — supports type unions (`:ok(text) | :error(text)`) and structural maps (`{name: text, age: number}`)

A function with no parameters omits `takes:`. A function that returns nothing uses `returns: none`. Parameters and returns use concrete types — type variables are only used in built-in signatures.

### Implementation (implement)

The agent-authored code behind a `define`.

```
implement file.read
  let raw = io.read_bytes(path)
  match raw
    none -> return none
    bytes -> return text.decode(bytes, encoding)
```

- Parameters are available as bindings (no re-declaration)
- No type annotations on locals — inferred from usage
- Must end with a `return` (explicit, no implicit returns). `return` always exits the `implement` block, even when inside a `match` arm or `if` branch
- Can call any defined function (built-in or agent-authored), including itself (recursion)
- The interpreter enforces a call depth limit to prevent infinite recursion. Exceeding it is an interpreter error. The limit is interpreter config, invisible to the agent

### Lambdas

Anonymous functions. Can be single-expression or multi-line.

```
-- Single-expression
fn(x) -> x * 2
fn(a, b) -> a + b
fn(item) -> item.name

-- Multi-line (last expression is the return value, no explicit return needed)
fn(tag) ->
  let matching = items |> list.filter(fn(item) -> text.contains(item, tag))
  {key: tag, value: matching}
```

Used primarily with list operations:

```
let names = people |> list.map(fn(p) -> p.name)
let adults = people |> list.filter(fn(p) -> p.age >= 18)
let total = prices |> list.fold(0, fn(sum, p) -> sum + p)
```

In lambdas, the last expression is implicitly returned. In `implement` blocks, `return` is explicit.

Lambdas capture bindings from their enclosing scope. Since all bindings are immutable, capture is always safe — no shared mutable state.

```
let threshold = 18
let adults = people |> list.filter(fn(p) -> p.age >= threshold)
-- threshold is captured from the outer scope
```

---

## 6. Namespaces

Functions are organized in a dot-separated hierarchy.

```
io.read
io.write
text.split
text.join
list.map
list.filter
inbox.read
inbox.summarize
health.check_plan
```

### File structure

Five layers, optimized for incremental discovery:

```
lumon/
  index.lumon              -- namespace names + one-line descriptions (always in context)
  manifests/
    io.lumon               -- define blocks for io.*
    text.lumon             -- define blocks for text.*
    inbox.lumon            -- define blocks for inbox.* (agent-authored)
    browser.lumon          -- define blocks for browser.* (plugin)
  impl/
    inbox.lumon            -- implement blocks for inbox.*
    health.lumon           -- implement blocks for health.*
  tests/
    inbox.lumon            -- test blocks for inbox.*
    health.lumon           -- test blocks for health.*
```

- **index.lumon** — one line per namespace (name + description). Always in context. Stays small regardless of how many functions exist.
- **manifests/** — complete function signatures (`define` blocks) per namespace. Loaded on demand when the agent needs to understand what a namespace offers.
- **impl/** — implementation code. Loaded on demand when calling a function. Built-in namespaces (`io`, `text`, `list`, `map`, `number`, `type`, `time`, `json`, `csv`) are implemented in the host language and have no files here.
- **tests/** — test blocks. Loaded when running tests, not during normal execution.

### Browsing

The agent discovers capabilities in three steps:
1. Read `index.lumon` — always in context, one line per namespace (~20 lines for 20 namespaces)
2. Load `manifests/<namespace>.lumon` — full signatures for the relevant namespace
3. Load `impl/<namespace>.lumon` — implementation, only when calling or extending

### Nesting

Namespaces can nest: `health.labs.latest`, `news.sources.tech`. No limit on depth, but convention is 2-3 levels max.

### Plugins

Plugins are self-contained directories that extend Lumon with capabilities that can't be expressed in the language itself — browser automation, database access, third-party APIs. Each plugin contains its own manifest, implementation, and executable scripts. The interpreter auto-discovers plugins from a `plugins/` directory, controlled by a `.lumon.json` config.

**Directory structure**:

```
target/
  .lumon.json            ← plugin access control + contracts
  sandbox/               ← Lumon agent workspace (working_dir)
    lumon/manifests/
    lumon/impl/
  plugins/               ← all available plugins
    browser/
      manifest.lumon     # define browser.search ...
      impl.lumon         # implement browser.search using plugin.exec
      search.py          # actual executable
    greet/
      manifest.lumon
      impl.lumon
      greet.py
```

**`.lumon.json` — plugin access control, contracts, and multi-instance**:

```json
{
  "plugins": {
    "zillow": {
      "plugin": "browser",
      "env": {
        "API_KEY": "sk-zillow-123",
        "BASE_URL": "https://api.zillow.com"
      },
      "search": {
        "url": "https://zillow.com/*",
        "max_results": [1, 50]
      }
    },
    "redfin": {
      "plugin": "browser",
      "env": {
        "API_KEY": "sk-redfin-456",
        "BASE_URL": "https://api.redfin.com"
      },
      "search": {
        "url": "https://redfin.com/*",
        "max_results": [1, 20]
      }
    },
    "greet": {}
  }
}
```

Top-level keys under `"plugins"` are **aliases** — the namespace the agent sees. Only listed plugins are loaded — unlisted ones are ignored. Empty `{}` means all functions enabled with no parameter contracts.

**Reserved keys** at the plugin instance level:

- `"plugin"` — source directory name in `plugins/`. If absent, the alias is the directory name (backward compatible).
- `"env"` — static environment variables passed to plugin scripts via subprocess env. Useful for API keys, base URLs, and other config that scripts need but agents shouldn't see.

Everything else is treated as function-level contracts/forced values.

**Multi-instance**: the same plugin directory can be registered multiple times under different aliases with different configs. Each alias gets its own contracts, forced values, and env vars.

**Contract types** — contract values are classified by shape:

- **Dynamic** (agent provides, system validates):
  - Text wildcard: `"https://zillow.com/*"` — string with `*`, `fnmatch` glob pattern
  - Number range: `[min, max]` — inclusive range for number args
  - Enum: `["option1", "option2"]` (list of strings) — allowed values for text args
- **Forced** (system injects, agent never sees):
  - Plain string (no `*`): `"sk-abc123"` — injected at the correct position
  - Plain number: `42` — injected
  - Plain boolean: `true` / `false` — injected

Contract violations are interpreter errors (halt execution with structured error).

**Forced values**: when a contract value is forced (plain string without `*`, plain number, plain boolean), the parameter is hidden from `lumon browse` output and the agent never provides it. The system injects the forced value at the correct position before contract validation. The implementation body sees all parameters (forced + agent-provided).

**Instance identity and environment variables**: each plugin instance receives a `LUMON_PLUGIN_INSTANCE` environment variable set to the alias name, so scripts can namespace their storage. Custom env vars from the `"env"` config are also merged into the subprocess environment.

**Plugin implementation**: plugin `impl.lumon` files use `plugin.exec(command, args)` to run scripts in the plugin's directory. `plugin.exec` is only callable from inside a plugin implementation — it errors anywhere else.

```
implement greet.hello
  let result = plugin.exec("python3 greet.py", {name: name})
  return result
```

**`plugin.exec` protocol**:

- **Input**: sends `args` map as JSON on stdin (just the map, no wrapper)
- **Output**: exit 0 + valid JSON on stdout = return value; non-zero exit = `:error(stderr[:1024])`
- **Scope**: only callable from inside a plugin's `impl.lumon` body; errors elsewhere
- **CWD**: runs in the plugin's directory
- **Timeout**: 30 seconds

**Output protocol** (exit-code wrapper):

| Scenario | Result |
| :---- | :---- |
| Exit 0 + valid JSON | Value returned to Lumon code |
| Exit 0 + invalid JSON | Interpreter error (`{"type": "error", ...}`) |
| Non-zero exit | `:error(stderr_message)` returned to Lumon code |
| Executable not found | Interpreter error |
| Timeout (30s) | Interpreter error |

On exit 0, stdout is parsed as JSON and deserialized into Lumon values (tag objects like `{"tag": "ok", "value": [...]}` are reconstituted as `:ok([...])`). On non-zero exit, the interpreter wraps stderr (trimmed, capped at 1KB) as `:error(message)`.

**Resolution order**: when a function is called, the interpreter resolves it in this order:

1. **Built-in** — `text.*`, `list.*`, `io.*`, etc.
2. **User-defined** — `implement` blocks (in-memory or auto-loaded from `lumon/impl/`)
3. **Fail** — `Undefined function` error

Plugin defines and implements are registered at startup, so they participate in step 2. If a user `implement` block in `sandbox/lumon/impl/` exists for a function that also has a plugin impl, the user impl takes precedence (loaded later by the lazy loader).

**Discovery**: `lumon browse` shows plugin aliases in the index. `lumon browse <alias>` shows the plugin's manifest with the alias namespace, dynamic contract annotations, and forced parameters hidden:

```
define zillow.search
  "Search the web"
  takes:
    url: text "URL to search"              [contract: https://zillow.com/*]
    max_results: number "Max results" = 10  [contract: 1-50]
  returns: :ok(list<map>) | :error(text)
```

(If `api_key` were a forced parameter, it would not appear in the output above.)

**Security properties**:

- Agent cannot create or modify plugins — `plugins/` and `.lumon.json` are author-controlled
- `plugin.exec` is scoped to plugin implementations — agent code cannot call it
- Contracts enforce parameter invariants before execution — violations are interpreter errors
- Every plugin capability has a `define` in its manifest — `lumon browse` reveals the full surface area
- Plugin scripts run with the same filesystem/network constraints as the host process

---

## 7. Tests

Test blocks verify function behavior. Discovered automatically by the interpreter.

```
test inbox.summarize
  let sample = ["Buy milk", "Schedule dentist", "Read paper"]
  let result = inbox.summarize(sample)
  assert list.length(result) <= 3
  assert text.contains(result[0], "milk") or text.contains(result[0], "dentist")

test inbox.summarize.empty
  let result = inbox.summarize([])
  assert result == []
```

### Assertions

`assert` takes a boolean expression. On failure, the interpreter reports:
- Which test failed
- The expression that was false
- The actual values of sub-expressions

### Conventions (FAST)

- **Fast** — no I/O, no network in tests. Use mock data.
- **Automated** — agent writes and runs them, no human intervention
- **Self-validating** — pass/fail only, no interpretation needed
- **Timely** — written alongside or before the implementation

### Regression

When an `implement` block is modified, the interpreter automatically runs all `test` blocks for that function. The new implementation is **rejected** if any test fails.

---

## 8. Comments

```
-- This is a comment
let x = 42  -- inline comment
```

Double dash, like Lua/Haskell. Single-line only. Block comments are not needed — if you need to explain something long, it should be a description on a `define`.

---

## 9. Built-in Primitives

These are implemented in the host language (Python), not in Lumon. They define the agent's reality.

Built-in signatures use type variables (`a`, `b`) for generic operations. The type checker infers concrete types at each call site.

### io

| Function | Signature | Description |
| :---- | :---- | :---- |
| `io.read` | `(path: text) -> :ok(text) \| :error(text)` | Read a file's contents |
| `io.write` | `(path: text, content: text) -> :ok \| :error(text)` | Write content to a file |
| `io.mkdir` | `(path: text) -> :ok \| :error(text)` | Create a directory (and intermediate parents) |
| `io.list_dir` | `(path: text, recursive: bool = false) -> :ok(list<text>) \| :error(text)` | List files in a directory (recursive returns relative paths) |
| `io.delete` | `(path: text) -> :ok \| :error(text)` | Delete a file |
| `io.delete_dir` | `(path: text) -> :ok \| :error(text)` | Delete a directory and all its contents |
| `io.find` | `(path: text, pattern: text) -> :ok(list<text>) \| :error(text)` | Find files matching a glob pattern (recursive) |
| `io.grep` | `(path: text, pattern: text) -> :ok(list<text>) \| :error(text)` | Search files for substring, returns `filepath:line:content` |
| `io.head` | `(path: text, n: number) -> :ok(text) \| :error(text)` | First n lines of a file |
| `io.tail` | `(path: text, n: number) -> :ok(text) \| :error(text)` | Last n lines of a file |
| `io.replace` | `(path: text, old: text, new: text) -> :ok \| :error(text)` | Replace all occurrences of old with new in a file |

All paths are relative to the **root directory**, which is the working directory where the interpreter is launched. The interpreter normalizes paths and resolves symlinks before checking — paths that resolve outside the root return `:error` (indistinguishable from "file not found"). The agent is not aware that path restrictions exist.

### git

| Function | Signature | Description |
| :---- | :---- | :---- |
| `git.status` | `() -> :ok(text) \| :error(text)` | Porcelain git status output |
| `git.log` | `(n: number) -> :ok(list<text>) \| :error(text)` | Last n commits as `"hash subject"` strings |
| `git.init` | `() -> :ok \| :error(text)` | Initialize a new git repository |
| `git.add` | `(path: text) -> :ok \| :error(text)` | Stage a file for the next commit |
| `git.commit` | `(message: text) -> :ok(text) \| :error(text)` | Create a commit, returns short hash |
| `git.diff` | `() -> :ok(text) \| :error(text)` | Show unstaged changes |
| `git.diff_staged` | `() -> :ok(text) \| :error(text)` | Show staged changes (index vs HEAD) |
| `git.branch` | `(name: text) -> :ok \| :error(text)` | Create a new branch |
| `git.branch_list` | `() -> :ok(list<text>) \| :error(text)` | List all local branches |
| `git.checkout` | `(ref: text) -> :ok \| :error(text)` | Switch to a branch or ref |
| `git.reset` | `(path: text) -> :ok \| :error(text)` | Unstage a file (keeps working tree; no-op if not staged) |
| `git.show` | `(ref: text) -> :ok(text) \| :error(text)` | Show commit details and stats |
| `git.tag` | `(name: text) -> :ok \| :error(text)` | Create a lightweight tag at HEAD |
| `git.tag_list` | `() -> :ok(list<text>) \| :error(text)` | List all tags |

Git functions are only available when a git backend is provided. In the CLI, this is automatic. The git backend runs real git commands via subprocess. Only local operations are exposed — no remote commands (push, pull, fetch, clone). Destructive operations (reset --hard, clean, branch -D) are excluded by design.

### text

**String interpolation**: `\(expr)` inside text literals evaluates the expression and implicitly calls `text.from` to convert non-text values.

```
let name = "Lumon"
let msg = "Welcome to \(name)"        -- "Welcome to Lumon"
let n = 3
let msg = "\(n) items found"          -- "3 items found"
let msg = "total: \(n * 2 + 1)"       -- "total: 7"
```

| Function | Signature | Description |
| :---- | :---- | :---- |
| `text.split` | `(s: text, sep: text) -> list<text>` | Split text by separator |
| `text.join` | `(items: list<text>, sep: text) -> text` | Join list items with separator |
| `text.contains` | `(s: text, sub: text) -> bool` | Check if text contains substring |
| `text.replace` | `(s: text, old: text, new: text) -> text` | Replace occurrences |
| `text.slice` | `(s: text, start: number, end: number) -> text` | Extract substring (0-based, end is exclusive). Out-of-bounds indices are clamped. |
| `text.length` | `(s: text) -> number` | Character count |
| `text.upper` | `(s: text) -> text` | Convert to uppercase |
| `text.lower` | `(s: text) -> text` | Convert to lowercase |
| `text.trim` | `(s: text) -> text` | Remove leading/trailing whitespace |
| `text.starts_with` | `(s: text, prefix: text) -> bool` | Check prefix |
| `text.ends_with` | `(s: text, suffix: text) -> bool` | Check suffix |
| `text.from` | `(value: a) -> text` | Convert any value to text |
| `text.match` | `(s: text, pattern: text) -> bool` | Glob match (`*`, `?`, `[abc]`, `[!abc]`) |
| `text.index_of` | `(s: text, sub: text) -> number \| none` | First position of substring, or none |
| `text.lines` | `(s: text) -> list<text>` | Split by newline |
| `text.split_first` | `(s: text, sep: text) -> map` | Split at first occurrence → `{before, after}` |
| `text.extract` | `(s: text, start: text, end: text) -> list<text>` | All segments between delimiters |
| `text.pad_start` | `(s: text, len: number, fill: text) -> text` | Left-pad to length |
| `text.pad_end` | `(s: text, len: number, fill: text) -> text` | Right-pad to length |
| `text.encode_url` | `(s: text) -> text` | URL-encode (percent-encoding) |
| `text.decode_url` | `(s: text) -> text` | Decode URL-encoded text |
| `text.encode_base64` | `(s: text) -> text` | Encode to base64 |
| `text.decode_base64` | `(s: text) -> text` | Decode base64 |
| `text.match_pattern` | `(s: text, pattern: tag) -> bool` | Match named pattern (`:email`, `:url`, `:iso_date`, `:phone`, `:number`) |
| `text.find_pattern` | `(s: text, pattern: tag) -> list<text>` | Find all occurrences of named pattern |

### list

| Function | Signature | Description |
| :---- | :---- | :---- |
| `list.map` | `(items: list<a>, f: fn(a) -> b) -> list<b>` | Apply function to each item |
| `list.filter` | `(items: list<a>, f: fn(a) -> bool) -> list<a>` | Keep items where f returns true |
| `list.fold` | `(items: list<a>, init: b, f: fn(b, a) -> b) -> b` | Reduce list to single value |
| `list.flat_map` | `(items: list<a>, f: fn(a) -> list<b>) -> list<b>` | Map then flatten one level |
| `list.sort` | `(items: list<a>) -> list<a>` | Sort in natural order (a must be text or number) |
| `list.sort_by` | `(items: list<a>, f: fn(a) -> b) -> list<a>` | Sort by key function |
| `list.take` | `(items: list<a>, n: number) -> list<a>` | First n items |
| `list.drop` | `(items: list<a>, n: number) -> list<a>` | All items after first n |
| `list.deduplicate` | `(items: list<a>) -> list<a>` | Remove duplicates (preserves order) |
| `list.length` | `(items: list<a>) -> number` | Item count |
| `list.contains` | `(items: list<a>, item: a) -> bool` | Check membership |
| `list.reverse` | `(items: list<a>) -> list<a>` | Reverse order |
| `list.flatten` | `(items: list<list<a>>) -> list<a>` | Flatten one level of nesting |
| `list.head` | `(items: list<a>) -> a \| none` | First item (or none) |
| `list.first` | `(items: list<a>) -> a \| none` | Alias for `list.head` |
| `list.tail` | `(items: list<a>) -> list<a>` | All items except first |
| `list.concat` | `(first: list<a>, second: list<a>) -> list<a>` | Concatenate two lists |
| `list.find` | `(items: list<a>, f: fn(a) -> bool) -> a \| none` | First item matching predicate |
| `list.any` | `(items: list<a>, f: fn(a) -> bool) -> bool` | Any item matches predicate |
| `list.all` | `(items: list<a>, f: fn(a) -> bool) -> bool` | All items match predicate |
| `list.zip` | `(a: list<a>, b: list<b>) -> list<{first, second}>` | Combine into pairs |
| `list.enumerate` | `(items: list<a>) -> list<{index, value}>` | Add index to each item |
| `list.group_by` | `(items: list<a>, f: fn(a) -> text) -> map<list<a>>` | Group by key function |
| `list.index_of` | `(items: list<a>, item: a) -> number \| none` | Position of item (or none) |
| `list.unique_by` | `(items: list<a>, f: fn(a) -> b) -> list<a>` | Remove duplicates by key |

### map

| Function | Signature | Description |
| :---- | :---- | :---- |
| `map.get` | `(m: map<a>, key: text) -> a \| none` | Get value by key (or none) |
| `map.set` | `(m: map<a>, key: text, value: a) -> map<a>` | Return new map with key set |
| `map.keys` | `(m: map<a>) -> list<text>` | All keys as list |
| `map.values` | `(m: map<a>) -> list<a>` | All values as list |
| `map.merge` | `(first: map<a>, second: map<a>) -> map<a>` | Merge two maps (second overwrites first) |
| `map.has` | `(m: map<a>, key: text) -> bool` | Check if key exists |
| `map.remove` | `(m: map<a>, key: text) -> map<a>` | Return new map without key |
| `map.entries` | `(m: map<a>) -> list<{key: text, value: a}>` | List of {key, value} maps |
| `map.map` | `(m: map<a>, f: fn(text, a) -> b) -> map<b>` | Transform values |
| `map.filter` | `(m: map<a>, f: fn(text, a) -> bool) -> map<a>` | Filter entries |
| `map.from_entries` | `(entries: list<{key, value}>) -> map<a>` | Build map from entries list |
| `map.size` | `(m: map<a>) -> number` | Entry count |

`map.*` functions operate on uniform maps (`map<a>`). For structural maps, use `.field` access, pattern matching, and spread syntax.

### number

| Function | Signature | Description |
| :---- | :---- | :---- |
| `number.round` | `(n: number) -> number` | Round to nearest integer |
| `number.floor` | `(n: number) -> number` | Round down |
| `number.ceil` | `(n: number) -> number` | Round up |
| `number.abs` | `(n: number) -> number` | Absolute value |
| `number.min` | `(a: number, b: number) -> number` | Smaller of two |
| `number.max` | `(a: number, b: number) -> number` | Larger of two |
| `number.parse` | `(s: text) -> number \| none` | Parse text to number (or none) |
| `number.random` | `() -> number` | Random float in [0, 1) |
| `number.random_int` | `(min: number, max: number) -> number` | Random integer in [min, max] inclusive |
| `number.pow` | `(base: number, exp: number) -> number` | Raise base to exponent |
| `number.sqrt` | `(n: number) -> number` | Square root |
| `number.log` | `(n: number) -> number` | Natural logarithm |
| `number.sign` | `(n: number) -> number` | Sign: 1, -1, or 0 |
| `number.truncate` | `(n: number) -> number` | Truncate toward zero |
| `number.clamp` | `(n: number, low: number, high: number) -> number` | Clamp between low and high |
| `number.mod` | `(a: number, b: number) -> number` | Modulo (remainder of a / b) |
| `number.format` | `(n: number, decimals: number) -> text` | Format number with fixed decimal places |
| `number.to_text` | `(n: number) -> text` | Number to text (no trailing .0) |
| `number.range` | `(start: number, end: number) -> list<number>` | Integer range [start, end] inclusive (max 10000) |
| `number.pi` | `() -> number` | The constant pi |
| `number.e` | `() -> number` | Euler's number |
| `number.inf` | `() -> number` | Positive infinity |

### type

| Function | Signature | Description |
| :---- | :---- | :---- |
| `type.of` | `(value: a) -> text` | Returns type name: "text", "number", etc. |
| `type.is` | `(value: a, t: text) -> bool` | Check if value is of type |

### log

| Function | Signature | Description |
| :---- | :---- | :---- |
| `log` | `(value: a) -> none` | Emit value to `"logs"` array in JSON output (execution continues) |

### time

All timestamps are Unix epoch milliseconds (UTC).

| Function | Signature | Description |
| :---- | :---- | :---- |
| `time.now` | `() -> number` | Current UTC timestamp in milliseconds |
| `time.wait` | `(ms: number) -> none` | Sleep for ms; error if ms < 0 or > 60000 |
| `time.format` | `(timestamp: number, pattern: text) -> text` | Format timestamp with strftime pattern |
| `time.parse` | `(text: text, pattern: text) -> number \| none` | Parse date string to timestamp (none on failure) |
| `time.since` | `(timestamp: number) -> number` | Milliseconds elapsed since timestamp |
| `time.date` | `() -> map` | Current UTC date as {year, month, day, hour, minute, second} |
| `time.add` | `(timestamp: number, ms: number) -> number` | Add ms to timestamp |
| `time.diff` | `(a: number, b: number) -> number` | Difference a - b in milliseconds |
| `time.timeout` | `(ms: number, fn() -> a) -> :ok(a) \| :timeout` | Run fn with timeout; error if ms < 0 or > 60000 |

### json

Parse and serialize JSON. Two layers: pure text functions for in-memory data, and file functions that go through `io` (inheriting its path sandboxing).

**Pure (text ↔ value):**

| Function | Signature | Description |
| :---- | :---- | :---- |
| `json.parse` | `(s: text) -> :ok(a) \| :error(text)` | Parse JSON text into a Lumon value |
| `json.to_text` | `(value: a) -> text` | Serialize any Lumon value to JSON text |
| `json.to_text_pretty` | `(value: a) -> text` | Serialize with indentation |

**File (sandboxed via `io`):**

| Function | Signature | Description |
| :---- | :---- | :---- |
| `json.read` | `(path: text) -> :ok(a) \| :error(text)` | Read a file and parse its contents as JSON |
| `json.write` | `(path: text, value: a) -> :ok \| :error(text)` | Serialize a value and write it as JSON |
| `json.write_pretty` | `(path: text, value: a) -> :ok \| :error(text)` | Serialize with indentation and write |

File functions are equivalent to `io.read` + `json.parse` and `json.to_text` + `io.write`. They exist for convenience and to ensure the agent always goes through `io` for file access — there is no separate file path.

**Type mapping:**

| JSON | Lumon |
| :---- | :---- |
| `string` | `text` |
| `number` | `number` |
| `boolean` | `bool` |
| `null` | `none` |
| `array` | `list` |
| `object` | `map` |

Round-trip: `json.parse(json.to_text(value)) == value` for all Lumon values except tags. Tags serialize as `{"tag": "name", "value": payload}` (same as the output protocol).

### csv

Parse and serialize CSV. Same two-layer pattern as `json` — pure text functions and sandboxed file functions through `io`.

**Pure (text ↔ value):**

| Function | Signature | Description |
| :---- | :---- | :---- |
| `csv.parse` | `(s: text) -> list<list<text>>` | Parse CSV text into rows of fields |
| `csv.parse_with_headers` | `(s: text) -> list<map<text>>` | Parse CSV using first row as keys — each row becomes a map |
| `csv.to_text` | `(rows: list<list<text>>) -> text` | Serialize rows to CSV text |
| `csv.to_text_with_headers` | `(headers: list<text>, rows: list<map<text>>) -> text` | Serialize maps to CSV with a header row |

**File (sandboxed via `io`):**

| Function | Signature | Description |
| :---- | :---- | :---- |
| `csv.read` | `(path: text) -> :ok(list<list<text>>) \| :error(text)` | Read and parse a CSV file |
| `csv.read_with_headers` | `(path: text) -> :ok(list<map<text>>) \| :error(text)` | Read and parse a CSV file using first row as keys |
| `csv.write` | `(path: text, rows: list<list<text>>) -> :ok \| :error(text)` | Serialize rows and write as CSV |
| `csv.write_with_headers` | `(path: text, headers: list<text>, rows: list<map<text>>) -> :ok \| :error(text)` | Serialize maps with headers and write as CSV |

All fields are text. The agent converts to/from numbers via `number.parse` / `number.to_text` as needed. CSV parsing handles quoting (RFC 4180): fields containing commas, newlines, or double quotes are enclosed in double quotes, and double quotes within fields are escaped as `""`.

---

## 10. Execution Model

1. The agent's context contains the language spec and `index.lumon` (namespace directory)
2. The agent uses Bash to run the `lumon` CLI — writing Lumon code inline, via stdin, or from files
3. The interpreter parses, type-checks, and executes
4. Results are returned to stdout as structured JSON
5. Agent-authored implementations are saved to disk and reloaded on next session

### Type checker

The interpreter runs a full type checker before execution. **All type errors are caught statically — none occur at runtime.**

Pipeline: **parse → type check → execute**.

The checker:
1. **Verifies function calls** match `define` signatures (argument types, argument count, return type)
2. **Infers local types** in `implement` blocks from literals, function return types, and operations — no annotations needed on locals
3. **Verifies operators** are applied to compatible types (e.g., `+` requires number+number or text+text)
4. **Checks list homogeneity** — all elements must be the same type
5. **Checks structural map access** — `.field` on a structural map must exist and yields the field's type. `.field` on a non-map value returns `none` (safe for `??` fallback)
6. **Checks tag exhaustiveness** — `match` on a value with a known tag set must cover all tags (or use `_`)
7. **Propagates type unions** — if `io.read` returns `:ok(text) | :error(text)`, the binding inherits that union, and using it without matching is a type error

Type errors are reported as interpreter errors (structured JSON, execution halts). The agent reads them and fixes the code.

```
-- Type error examples the checker catches:
let x = 42 + "hello"           -- error: + requires number+number or text+text
let y = list.head([1, 2, 3])
let z = y + 1                  -- error: y is number | none, must handle none first
let r = io.read("f.md")
let c = text.length(r)         -- error: r is :ok(text) | :error(text), not text
```

### CLI interface

The interpreter is a command-line program. Any agent with shell access can use it — no special tool registration, no SDK, no API. Works with Claude Code, Cursor, custom orchestrators, anything.

**Run code:**

```bash
# Inline code as argument
lumon 'inbox.read()'

# From stdin (pipes work)
echo 'inbox.read()' | lumon

# From file
lumon impl/inbox.lumon
```

**Discovery:**

```bash
# Show index (all namespaces, one line each)
lumon browse

# Show manifest for a namespace (all define blocks)
lumon browse inbox
```

**Tests:**

```bash
# Run tests for a namespace
lumon test inbox

# Run all tests
lumon test
```

**Save implementations:**

```bash
# The interpreter detects implement/define/test blocks and saves them
# to the appropriate files (impl/, manifests/, tests/)
lumon 'implement inbox.read
  match io.read(path)
    :error(_) -> return :ok([])
    :ok(content) -> return :ok(content |> text.split("\n"))
'
```

### Output protocol

All output is structured JSON to stdout.

**Value serialization:**

| Lumon type | JSON representation |
| :---- | :---- |
| `text` | JSON string |
| `number` | JSON number |
| `bool` | JSON boolean |
| `none` | JSON null |
| `list<T>` | JSON array |
| structural map | JSON object |
| `map<T>` | JSON object |
| `:tag` | `{"tag": "tag"}` |
| `:tag(value)` | `{"tag": "tag", "value": <serialized value>}` |

**Success:**

```json
{"type": "result", "value": ["Buy milk", "Call dentist"]}
```

Tag result example:

```json
{"type": "result", "value": {"tag": "ok", "value": "file contents here"}}
```

**Error (interpreter error — execution halts):**

```json
{
  "type": "error",
  "function": "inbox.read",
  "trace": ["inbox.read"],
  "inputs": {"path": "INBOX.md"},
  "message": "Undefined variable: raw_content"
}
```

**Ask (execution suspended, waiting for agent judgment):**

```json
{
  "type": "ask",
  "session": "a3f2e1b9",
  "prompt": "Which of these should I handle first?\n\nContext data: .lumon_comm/a3f2e1b9/ask_context.json",
  "expects": {"action": "text", "item": "text"},
  "context_file": ".lumon_comm/a3f2e1b9/ask_context.json",
  "response_file": ".lumon_comm/a3f2e1b9/ask_response.json"
}
```

The agent reads the context file, reasons about it, writes a response to the response file, and resumes:

```bash
echo '{"action": "process", "item": "Pay bill"}' > .lumon_comm/a3f2e1b9/ask_response.json
lumon respond a3f2e1b9
```

This returns the next output — another ask, a spawn batch, or a final result.

**Spawn batch (execution suspended, requesting sub-agents):**

```json
{
  "type": "spawn_batch",
  "session": "a3f2e1b9",
  "spawns": [
    {
      "spawn_id": "spawn_0",
      "prompt": "Analyze article for bias\n\nContext data: .lumon_comm/a3f2e1b9/spawn_0_context.json",
      "expects": {"bias": "number", "summary": "text"},
      "context_file": ".lumon_comm/a3f2e1b9/spawn_0_context.json",
      "response_file": ".lumon_comm/a3f2e1b9/spawn_0_response.json"
    }
  ]
}
```

The agent reads context files, spawns sub-agents, and writes responses to the indicated files:

```bash
echo '{"bias": 0.3, "summary": "..."}' > .lumon_comm/a3f2e1b9/spawn_0_response.json
lumon respond a3f2e1b9
```

### File-based communication

When execution suspends (ask or spawn), Lumon writes large context data to files under `.lumon_comm/<session>/` instead of inlining it in the JSON output. This keeps the stdout output small and readable.

- **Context files** (e.g. `spawn_0_context.json`, `ask_context.json`) — written by Lumon, read by the agent
- **Response files** (e.g. `spawn_0_response.json`, `ask_response.json`) — written by the agent, read by Lumon on `lumon respond`

The session ID is an 8-character hex string, unique per execution. It's included in the output so the orchestrator knows which directory to use. Pass it to `lumon respond <session>` to resume execution.

### Suspension and resumption

When execution suspends on `ask` or `spawn`, the interpreter prints the suspension envelope to stdout and returns control to the agent immediately. The process stays alive in the background, waiting for responses.

The agent writes response files to the paths indicated in the envelope, then runs `lumon respond`. This prints the next output — another suspension envelope if execution suspends again, or the final result. The comm directory is cleaned up automatically after execution completes.

### Pending session detection

If a Lumon script is run from a file and already has a pending session (an ask or spawn awaiting a response), the interpreter refuses to re-run and returns an error:

```json
{
  "type": "error",
  "message": "Script has pending session a3f2e1b9. Use 'lumon respond' to resume or 'lumon respond --clear' to discard."
}
```

This prevents accidental re-execution that would silently discard in-progress work. The agent must explicitly respond (`lumon respond`) or clear the session (`lumon respond --clear`).

- **File-based runs only** — inline code and stdin are not tracked
- **Script marker file** — `script.txt` in the session directory associates it with the source script
- **Clear a session** — `lumon respond --clear` discards the session without resuming; auto-detects if only one session exists

### Concurrency

All code runs sequentially except `spawn`, which fires parallel sub-agents and blocks until all respond. See section 4 for full details.

### Error model

Two kinds of errors, cleanly separated:

**Recoverable errors** — expected failure modes in primitives (file not found, URL blocked, parse failure). Handled within the Lumon program via tag returns. Execution continues.

```
let result = io.write("path.md", content)
match result
  :ok -> log("saved")
  :error(m) -> log("write failed: \(m)")
```

Built-in primitives return tags like `:ok | :error(text)` for operations that can fail. The caller handles them with `match`. The interpreter does not halt — this is normal control flow.

**Interpreter errors** — bugs in the Lumon code itself: undefined variable, type mismatch at a function boundary, calling an undefined function. The program cannot continue. The interpreter halts and emits structured error JSON to stdout.

```json
{
  "type": "error",
  "function": "inbox.read",
  "trace": ["inbox.read", "io.read"],
  "inputs": {"path": "INBOX.md"},
  "message": "Undefined variable: raw_content"
}
```

The agent reads interpreter errors like a developer reads a traceback — function, inputs, stack trace, message — and self-heals by rewriting the implementation.

| | Recoverable | Interpreter |
| :---- | :---- | :---- |
| Cause | Expected failure in a primitive | Bug in Lumon code |
| Mechanism | Tag return (`:error(msg)`) | Structured JSON to stdout |
| Execution | Continues, caller handles via `match` | Halts |
| Who fixes | The Lumon program | The agent (rewrites implementation) |
| Examples | File not found, URL blocked | Undefined variable, type mismatch |

---

## 11. Reserved Words

```
let, define, implement, test, takes, returns, return, match, if, else,
with, then, ask, spawn, fork, context, expects,
fn, assert, true, false, none, and, or, not
```

---

## Appendix: Grammar (informal)

```
program      = (define | implement | test | expression)*

define       = "define" namespace_path description
               ["takes:" parameter+]
               "returns:" type description

implement    = "implement" namespace_path body

test         = "test" namespace_path body

parameter    = name ":" type description ["=" expression]

body         = (binding | return | assert | expression)+

binding      = "let" name "=" expression
return       = "return" expression
assert       = "assert" expression

expression   = ask_expr | spawn_expr | with_expr | match_expr | if_expr | lambda | pipe | binary | call | access | literal | name
ask_expr     = "ask" text ["context:" expression] ["expects:" type_shape]
spawn_expr   = "spawn" expression  -- expression must evaluate to a list of task maps
with_expr    = "with" (name "=" expression)+ "then" expression "else" expression
pipe         = expression "|>" call
match_expr   = "match" expression (pattern ["if" expression] "->" (expression | NEWLINE INDENT body DEDENT))+
if_expr      = "if" expression body ["else" body]
lambda       = "fn" "(" params ")" "->" expression | "fn" "(" params ")" "->" NEWLINE INDENT body DEDENT
binary       = expression operator expression
call         = namespace_path "(" arguments ")"
access       = expression "." name | expression "[" expression "]"

literal      = number | text | bool | none | list | map | tag
tag          = ":" name ["(" (expression ("," expression)*)? ")"]
list         = "[" (expression ("," expression)*)? "]"
map          = "{" (map_entry ("," map_entry)*)? "}"
map_entry    = "..." expression | name ":" expression

type         = "text" | "number" | "bool" | "none" | list_type | map_type | struct_type | tag_type | fn_type | type_union | type_var
list_type    = "list" "<" type ">"
map_type     = "map" "<" type ">"
struct_type  = "{" name ":" type ("," name ":" type)* "}"
tag_type     = ":" name ["(" type ")"]
fn_type      = "fn" "(" type ("," type)* ")" "->" type
type_union   = type "|" type
type_var     = lowercase_letter

operator     = "+" | "-" | "*" | "/" | "%" | "==" | "!=" | "<" | ">" | "<=" | ">=" | "and" | "or" | "|>" | "??"

comment      = "--" (anything until end of line)
```

---

## Appendix: Examples

### 1. Bindings and expressions

```
let name = "Lumon"
let version = 0.1
let greeting = "Welcome to \(name) v\(version)"
return greeting
-- "Welcome to Lumon v0.1"
```

### 2. Lists and pipes

```
let numbers = [5, 3, 8, 1, 9, 2, 7]

let top_3 = numbers
  |> list.sort
  |> list.reverse
  |> list.take(3)

return top_3
-- [9, 8, 7]
```

### 3. Maps and pattern matching

```
let response = {status: "ok", data: {title: "Lumon spec", words: 2500}}

let summary = match response
  {status: "ok", data: d} -> "\(d.title) (\(d.words) words)"
  {status: "error", msg: m} -> "Error: \(m)"
  _ -> "Unknown response"

return summary
-- "Lumon spec (2500 words)"
```

### 4. Read and process a file

```
let result = io.read("INBOX.md")

match result
  :error(m) -> return :error("Inbox not found: \(m)")
  :ok(content) ->
    let items = content
      |> text.split("\n")
      |> list.filter(fn(l) -> text.starts_with(l, "- "))
      |> list.map(fn(l) -> text.slice(l, 2, text.length(l)))

    return :ok({items: items, count: list.length(items)})
-- :ok({items: ["Buy milk", "Call dentist", "Read paper"], count: 3})
```

### 5. Define and implement a function

```
define inbox.read
  "Read inbox items as a list of text entries"
  takes:
    path: text "Path to the inbox file" = "INBOX.md"
  returns: :ok(list<text>) | :error(text) "List of inbox item strings, or error"

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

test inbox.read
  -- assumes test fixture at "test/inbox.md" containing:
  -- - First item
  -- - Second item
  -- Some non-item line
  let result = inbox.read("test/inbox.md")
  match result
    :ok(items) ->
      assert list.length(items) == 2
      assert items[0] == "First item"
    :error(_) -> assert false

test inbox.read.missing
  let result = inbox.read("nonexistent.md")
  match result
    :error(_) -> assert true
    :ok(_) -> assert false
```

### 6. Composing multiple functions

Building on previous implementations that the agent has already written:

```
define inbox.categorize
  "Categorize inbox items by tag"
  takes:
    items: list<text> "List of inbox item strings"
  returns: map<list<text>> "Map from tag to list of items"

implement inbox.categorize
  let tags = ["#personal", "#errand", "#admin", "#social"]

  let categorized = tags
    |> list.map(fn(tag) ->
      let matching = items
        |> list.filter(fn(item) -> text.contains(item, tag))
      {key: tag, value: matching}
    )
    |> list.fold({}, fn(acc, entry) ->
      map.set(acc, entry.key, entry.value)
    )

  let untagged = items
    |> list.filter(fn(item) ->
      tags |> list.filter(fn(t) -> text.contains(item, t)) |> list.length == 0
    )

  return map.set(categorized, "#uncategorized", untagged)

test inbox.categorize
  let items = ["Buy milk #errand", "Call mom #personal", "Fix bug", "Dinner with Ale #social"]
  let result = inbox.categorize(items)
  assert list.length(map.get(result, "#errand")) == 1
  assert list.length(map.get(result, "#uncategorized")) == 1
  assert text.contains(map.get(result, "#uncategorized")[0], "Fix bug")
```

### 7. Full workflow: web to vault

An agent-authored function that fetches news from the web and writes a summary to the vault. Composes multiple previously implemented functions.

```
define news.fetch_and_summarize
  "Fetch articles from a source URL and write a summary to the vault"
  takes:
    source_url: text "URL of the news source"
    output_path: text "Vault path to write the summary"
    max_articles: number "Maximum articles to include" = 5
  returns: :ok({articles: number, path: text}) | :error(text) "Summary of what was written, or error"

implement news.fetch_and_summarize
  let page = web.fetch(source_url)
  match page
    :error(m) -> return :error("Could not fetch \(source_url): \(m)")
    :ok(html) ->
      -- extract article links and titles (agent-authored helper)
      let articles = html
        |> web.extract_links
        |> list.filter(fn(a) -> a.type == "article")
        |> list.take(max_articles)

      -- fetch each article's content (recoverable — skip failures)
      let contents = articles
        |> list.map(fn(a) ->
          match web.fetch(a.url)
            :ok(body) -> {...a, body: body}
            :error(_) -> {...a, body: "Could not fetch"}
        )

      -- format as markdown
      let header = "# News Summary\n> Fetched from \(source_url)\n\n---\n\n"
      let sections = contents
        |> list.map(fn(a) -> "## \(a.title)\n\n\(text.slice(a.body, 0, 500))\n\n---\n")
        |> text.join("\n")

      -- write to vault
      let markdown = header + sections
      match io.write(output_path, markdown)
        :error(m) -> return :error("Could not write: \(m)")
        :ok ->
          return :ok({
            articles: list.length(articles),
            path: output_path
          })

test news.fetch_and_summarize.formats_correctly
  -- unit test with mock data (no actual I/O)
  let articles = [
    {title: "AI Update", body: "Content here", url: "http://example.com/1", type: "article"},
    {title: "Tech News", body: "More content", url: "http://example.com/2", type: "article"}
  ]
  let sections = articles
    |> list.map(fn(a) -> "## \(a.title)\n\n\(text.slice(a.body, 0, 500))\n\n---\n")
    |> text.join("\n")
  assert text.contains(sections, "## AI Update")
  assert text.contains(sections, "## Tech News")
```

### 8. Flattening nested logic with `with` and `??`

Without `with`, chained operations that might fail produce deeply nested match blocks. The `with` block chains fallible steps — each line feeds the next, any `none` jumps to `else`. The `??` operator provides a default for single none-checks.

```
implement inbox.process_and_enrich
  "Read inbox, enrich each item with web context, group by tag"
  let result = io.read("INBOX.md")
  match result
    :error(m) -> return :error("Inbox not found: \(m)")
    :ok(content) ->
      let items = content
        |> text.split("\n")
        |> list.filter(fn(l) -> text.starts_with(l, "- "))
        |> list.map(fn(item) ->
          let clean = text.slice(item, 2, text.length(item))

          -- with block: chain fallible steps, bail to else on any none
          let context = with
            page = web.fetch("https://search.api/q=\(clean)")
            body = match page
              :ok(t) -> t
              :error(_) -> none
            lines = body |> text.split("\n")
            summary = lines
              |> list.filter(fn(l) -> text.contains(l, "summary"))
              |> list.head
          then
            summary
          else
            "No context available"

          let tag = match clean
            _ if text.contains(clean, "#errand") -> "errand"
            _ if text.contains(clean, "#personal") -> "personal"
            _ -> "uncategorized"

          {item: clean, context: context, tag: tag}
        )

      -- ?? operator: default value when expression is none
      let grouped = items
        |> list.fold({}, fn(acc, item) ->
          let existing = map.get(acc, item.tag) ?? []
          map.set(acc, item.tag, list.concat(existing, [item]))
        )

      return :ok(grouped)
```

### 9. Parallel sub-agents with spawn and ask

Combines `spawn` for parallel independent reasoning and `ask` for a judgment call by the main agent. Shows the full code → agent → code → agent → code flow.

```
define news.analyze_and_curate
  "Analyze articles via sub-agents, then ask main agent to curate"
  takes:
    source_path: text "Path to the source articles file"
    output_path: text "Path to write curated report"
  returns: :ok({kept: number, removed: number}) | :error(text) "Summary with counts, or error"

implement news.analyze_and_curate
  let source = io.read(source_path)
  match source
    :error(m) -> return :error(m)
    :ok(raw) ->
      let articles = raw |> text.split("\n---\n")

      -- Spawn sub-agents to analyze each article (all run in parallel)
      let analyses = spawn (articles |> list.map(fn(a) -> {
        prompt: "Analyze this article for bias and extract key claims",
        context: a
      }))

      -- Ask main agent to curate (judgment call)
      let curated = ask
        "Here are the analyses. Which sources are trustworthy? Remove biased ones."
        context: analyses
        expects: list

      -- Format and write
      let report = curated
        |> list.map(fn(a) -> "## \(a.source)\n\(a.summary)\n- Claims: \(text.join(a.claims, ", "))\n")
        |> text.join("\n---\n")

      match io.write(output_path, "# Curated Sources\n\n" + report)
        :error(m) -> return :error(m)
        :ok ->
          return :ok({
            kept: list.length(curated),
            removed: list.length(analyses) - list.length(curated)
          })
```

### 10. Plugin function

A plugin function backed by an external script. The project author creates a self-contained plugin directory with a manifest, implementation, and scripts. The agent calls it like any other function.

`plugins/browser/manifest.lumon`:
```
define browser.search
  "Search for homes on a real estate site"
  takes:
    query: text "Search query"
    max_results: number "Maximum listings to return" = 10
  returns: :ok(list<{address: text, price: number}>) | :error(text)
    "Search results or error"
```

`plugins/browser/impl.lumon`:
```
implement browser.search
  let result = plugin.exec("python3 search.py", {query: query, max_results: max_results})
  return result
```

`plugins/browser/search.py`:
```python
import json, sys

args = json.load(sys.stdin)
query = args["query"]
max_results = args["max_results"]

# ... do actual work ...
results = [{"address": "123 Main St", "price": 450000}]

json.dump({"tag": "ok", "value": results}, sys.stdout)
```

Agent-authored Lumon code that calls the plugin:
```
implement search.homes
  let results = browser.search(query, max_results)
  match results
    :ok(listings) -> return listings |> list.take(5)
    :error(msg) -> return :error("search failed: " + msg)
```
