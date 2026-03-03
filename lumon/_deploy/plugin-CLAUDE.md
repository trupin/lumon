# Lumon Plugin Agent Instructions

You are an agent that writes plugins for a Lumon project. Plugins are standalone scripts that extend the Lumon agent's capabilities through the bridge system. You operate from the `plugins/` directory and register your plugins with the Lumon agent in the sibling `sandbox/` directory.

## What is a plugin?

A plugin is an executable script that:
1. Reads a JSON request from stdin
2. Does useful work (web requests, database queries, file processing, etc.)
3. Writes a JSON response to stdout
4. Exits with code 0 on success, non-zero on error

The Lumon interpreter calls your plugin as a subprocess whenever the Lumon agent invokes the corresponding bridged function.

## Plugin protocol

### Input (stdin)

Your plugin receives a single JSON object:

```json
{
  "function": "search.web",
  "args": {
    "query": "Austin TX",
    "max_results": 10
  }
}
```

- `function`: the fully qualified function name (namespace.name)
- `args`: a map of named arguments matching the `define` signature

### Output (stdout)

Write a single JSON value to stdout.

**Success** — return a value directly or wrap in a tag:

```json
{"tag": "ok", "value": ["result1", "result2"]}
```

**Recoverable error** — return an error tag:

```json
{"tag": "error", "value": "connection timed out"}
```

**Plain values** work too — numbers, strings, lists, maps:

```json
"Hello, World!"
```

### Exit codes

| Exit code | Result in Lumon |
| :--- | :--- |
| 0 + valid JSON | Value returned to Lumon code |
| 0 + invalid JSON | Interpreter error (bug in your plugin) |
| Non-zero | `:error(stderr_message)` returned to Lumon code |

### Rules

- Read ALL of stdin before processing (the interpreter closes stdin after writing)
- Write ONLY valid JSON to stdout — no debug prints, no extra text
- Use stderr for debug output or error messages
- Keep execution under 30 seconds (the interpreter enforces a timeout)

## How to create a plugin

### Step 1: Write the plugin script

Create a Python file in this directory:

```python
#!/usr/bin/env python3
"""Greet someone by name."""
import json
import sys

request = json.load(sys.stdin)
name = request["args"]["name"]

json.dump(f"Hello, {name}!", sys.stdout)
```

### Step 2: Create the manifest

Create a manifest at `../sandbox/lumon/manifests/<namespace>.lumon` that defines the function signature. This is what the Lumon agent sees when it runs `browse`:

```
define greet.hello
  "Greet someone by name"
  takes:
    name: text "The name to greet"
  returns: text "The greeting"
```

**Manifest rules:**
- One namespace per file (all `greet.*` functions go in `greet.lumon`)
- Each function needs: description, typed parameters, return type
- Parameters: `name: type "description"` with optional `= default_value`
- Available types: `text`, `number`, `bool`, `list<T>`, `map`, `none`
- Use `:ok(T) | :error(text)` for functions that can fail

### Step 3: Register the bridge

Add a bridge declaration to `../sandbox/lumon/bridges.lumon`:

```
bridge greet.hello
  run: "python3 ../plugins/greet_hello.py"
```

**Path convention**: bridge `run:` commands execute with the working directory set to `sandbox/`. Since your plugins live in `plugins/` (a sibling of `sandbox/`), always use `../plugins/` in the path.

### Step 4: Update the namespace index

If this is a new namespace, add it to `../sandbox/lumon/index.lumon`:

```
greet "Greeting utilities"
```

Skip this if the namespace already exists in the index.

## How to test

### Test the plugin directly

```bash
echo '{"function": "greet.hello", "args": {"name": "World"}}' | python3 greet_hello.py
```

Expected output:
```json
"Hello, World!"
```

### Test through the Lumon interpreter

```bash
lumon --working-dir ../sandbox 'return greet.hello("World")'
```

Expected output:
```json
{"type": "result", "value": "Hello, World!"}
```

### Test error handling

Make sure your plugin handles bad input gracefully — exit non-zero or return an error tag:

```bash
echo '{"function": "greet.hello", "args": {}}' | python3 greet_hello.py
```

## File locations

| What | Path from `plugins/` |
| :--- | :--- |
| Plugin scripts | `./<script>.py` |
| Function manifests | `../sandbox/lumon/manifests/<ns>.lumon` |
| Bridge declarations | `../sandbox/lumon/bridges.lumon` |
| Namespace index | `../sandbox/lumon/index.lumon` |

## Complete example: web search plugin

### 1. Plugin script (`web_search.py`)

```python
#!/usr/bin/env python3
"""Search the web."""
import json
import sys
import urllib.request
import urllib.parse

request = json.load(sys.stdin)
query = request["args"]["query"]
max_results = request["args"].get("max_results", 5)

try:
    url = f"https://api.example.com/search?q={urllib.parse.quote(query)}&limit={max_results}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    results = [{"title": r["title"], "url": r["url"]} for r in data["results"]]
    json.dump({"tag": "ok", "value": results}, sys.stdout)
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
```

### 2. Manifest (`../sandbox/lumon/manifests/search.lumon`)

```
define search.web
  "Search the web for information"
  takes:
    query: text "Search query"
    max_results: number "Maximum results to return" = 5
  returns: :ok(list<map>) | :error(text) "Search results or error"
```

### 3. Bridge (`../sandbox/lumon/bridges.lumon`)

```
bridge search.web
  run: "python3 ../plugins/web_search.py"
```

### 4. Index entry (`../sandbox/lumon/index.lumon`)

```
search "Web search capabilities"
```

### 5. How the Lumon agent uses it

Once registered, the Lumon agent can call your plugin like any other function:

```
implement find.homes
  let results = search.web(query, 10)
  match results
    :ok(listings) -> return listings |> list.take(5)
    :error(msg) -> return :error("search failed: " + msg)
```

## Tips

- **One script per function** is simplest, but a single script can serve multiple functions by checking `request["function"]`
- **Use tags** (`:ok`/`:error`) for functions that can fail — it lets the Lumon agent handle errors with `match`
- **Test locally first** with `echo ... | python3` before wiring up the bridge
- **Check stderr** if a bridge call returns `:error` — your plugin's stderr becomes the error message
- **Read the Lumon spec** with `lumon spec` to understand the type system and language features
