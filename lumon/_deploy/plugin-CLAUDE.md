# Lumon Plugin Agent Instructions

You are an agent that writes plugins for a Lumon project. Plugins are self-contained directories that extend the Lumon agent's capabilities. Each plugin lives in its own directory under `plugins/` with a manifest, implementation, and scripts. The interpreter auto-discovers plugins listed in `.lumon.json`.

## What is a plugin?

A plugin is a self-contained directory containing:

1. **`manifest.lumon`** — `define` blocks declaring function signatures (what the agent sees)
2. **`impl.lumon`** — `implement` blocks that call `plugin.exec` to run scripts
3. **Script files** (e.g. `.py`) — the actual executables that do the work

The plugin's `impl.lumon` uses `plugin.exec(command, args)` to run scripts in the plugin's directory. The Lumon agent cannot call `plugin.exec` directly — it only works inside plugin implementations.

## Plugin directory structure

```
plugins/
  greet/
    manifest.lumon     # define greet.hello ...
    impl.lumon         # implement greet.hello using plugin.exec
    greet.py           # actual script
  browser/
    manifest.lumon
    impl.lumon
    search.py
```

## plugin.exec protocol

### How impl.lumon calls scripts

```
implement greet.hello
  let result = plugin.exec("python3 greet.py", {name: name})
  return result
```

`plugin.exec(command, args)`:
- **command**: shell command to run (executed in the plugin's directory)
- **args**: map sent as JSON on stdin (just the map, no wrapper)

### Script input (stdin)

Your script receives a plain JSON map:

```json
{"name": "World", "max_results": 10}
```

### Script output (stdout)

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
| 0 + invalid JSON | Interpreter error (bug in your script) |
| Non-zero | `:error(stderr_message)` returned to Lumon code |

### Rules

- Read ALL of stdin before processing (the interpreter closes stdin after writing)
- Write ONLY valid JSON to stdout — no debug prints, no extra text
- Use stderr for debug output or error messages
- Keep execution under 5 minutes (the interpreter enforces a timeout)

## Understanding the Lumon agent

Your plugins are consumed by a Lumon agent operating in `../sandbox/`. Before writing a plugin, explore the parent to understand how it will be used:

- **`../CLAUDE.md`** — The Lumon agent's instructions
- **`../sandbox/lumon/index.lumon`** — The namespace index
- **`../sandbox/lumon/manifests/`** — Existing function signatures
- **`../sandbox/lumon/impl/`** — The agent's implementations
- **`../.lumon.json`** — Plugin access control and contracts
- **`../sandbox/`** — Data files the agent works with

Start by reading `../CLAUDE.md` and browsing existing manifests. Design your plugin's API to match what the Lumon agent already expects — same tag patterns (`:ok`/`:error`), same naming conventions, same level of granularity.

## How to create a plugin

### Step 1: Create the plugin directory

```
plugins/<namespace>/
```

### Step 2: Write the manifest

Create `manifest.lumon` with `define` blocks:

```
define greet.hello
  "Greet someone by name"
  takes:
    name: text "The name to greet"
  returns: text "The greeting"
```

**Manifest rules:**
- Namespace matches directory name (all `greet.*` functions go in `greet/manifest.lumon`)
- Each function needs: description, typed parameters, return type
- Parameters: `name: type "description"` with optional `= default_value`
- Available types: `text`, `number`, `bool`, `list<T>`, `map`, `none`
- Use `:ok(T) | :error(text)` for functions that can fail

### Step 3: Write the implementation

Create `impl.lumon` that uses `plugin.exec`:

```
implement greet.hello
  let result = plugin.exec("python3 greet.py", {name: name})
  return result
```

### Step 4: Write the script

Create the executable script:

```python
#!/usr/bin/env python3
"""Greet someone by name."""
import json
import sys

args = json.load(sys.stdin)
name = args["name"]

json.dump(f"Hello, {name}!", sys.stdout)
```

### Step 5: Register in .lumon.json

Add the plugin to `../.lumon.json`:

```json
{
  "plugins": {
    "greet": {}
  }
}
```

Empty `{}` means all functions enabled with no parameter contracts. You can add contracts to restrict parameter values — see "Contracts" below.

## Contracts and forced values

The `.lumon.json` file can define contracts that restrict parameter values, or forced values that the system injects automatically. Contract violations are interpreter errors — the script never runs.

```json
{
  "plugins": {
    "browser": {
      "search": {
        "url": "https://zillow.com/*",
        "max_results": [1, 50]
      }
    }
  }
}
```

### Contract classification

Contract values are classified by shape:

**Dynamic** (agent provides, system validates):
- **Text wildcard**: `"https://zillow.com/*"` — glob pattern matched against text args (has `*`)
- **Number range**: `[1, 50]` — inclusive range for number args
- **Enum**: `["fast", "thorough"]` — allowed values for text args

**Forced** (system injects, agent never sees):
- **Plain string**: `"sk-abc123"` — no `*`, injected at the correct parameter position
- **Plain number**: `42` — injected
- **Plain boolean**: `true` / `false` — injected

### How forced values work

When a parameter has a forced value:
1. The agent sees a reduced signature — forced params are hidden from `lumon browse`
2. The agent calls with args for visible params only
3. The system reconstructs full args by interleaving forced values at correct positions
4. Dynamic contracts are validated on the full args
5. The implementation body sees all parameters (forced + agent-provided)

### How agents see contracts

When the agent runs `lumon browse <namespace>`, dynamic contracts are shown as annotations and forced params are hidden:

```
define browser.search
  "Search the web"
  takes:
    url: text "URL to search"              [contract: https://zillow.com/*]
    max_results: number "Max results" = 10  [contract: 1-50]
  returns: :ok(list<map>) | :error(text)
```

## Multi-instance plugins

The same plugin directory can be registered multiple times under different aliases with different configs. This lets project authors mount a generic plugin (e.g., `browser`) as multiple specialized instances (e.g., `zillow` and `redfin`).

```json
{
  "plugins": {
    "zillow": {
      "plugin": "browser",
      "env": {"API_KEY": "sk-zillow-123"},
      "search": {"url": "https://zillow.com/*"}
    },
    "redfin": {
      "plugin": "browser",
      "env": {"API_KEY": "sk-redfin-456"},
      "search": {"url": "https://redfin.com/*"}
    }
  }
}
```

- `"plugin"` — source directory name. If absent, the config key is the directory name (backward compatible)
- `"env"` — static environment variables passed to plugin scripts via subprocess env

## Instance identity and environment variables

Each plugin instance receives environment variables in the subprocess:

- **`LUMON_PLUGIN_INSTANCE`** — the alias name (e.g., `"zillow"`), so scripts can namespace storage
- **Custom env vars** from `"env"` config — API keys, base URLs, etc.

```python
import os
instance = os.environ.get("LUMON_PLUGIN_INSTANCE", "")
api_key = os.environ.get("API_KEY", "")
cache_dir = f"/tmp/lumon-{instance}"
```

## How to test

### Test the script directly

```bash
echo '{"name": "World"}' | python3 greet.py
```

### Test through the Lumon interpreter

```bash
lumon --working-dir ../sandbox 'return greet.hello("World")'
```

Expected output:
```json
{"type": "result", "value": "Hello, World!"}
```

## Complete example: web search plugin

### 1. Directory structure

```
plugins/search/
  manifest.lumon
  impl.lumon
  web_search.py
```

### 2. Manifest (`manifest.lumon`)

```
define search.web
  "Search the web for information"
  takes:
    query: text "Search query"
    max_results: number "Maximum results to return" = 5
  returns: :ok(list<map>) | :error(text) "Search results or error"
```

### 3. Implementation (`impl.lumon`)

```
implement search.web
  let result = plugin.exec("python3 web_search.py", {query: query, max_results: max_results})
  return result
```

### 4. Script (`web_search.py`)

```python
#!/usr/bin/env python3
"""Search the web."""
import json
import sys
import urllib.request
import urllib.parse

args = json.load(sys.stdin)
query = args["query"]
max_results = args.get("max_results", 5)

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

### 5. Config (`.lumon.json`)

```json
{
  "plugins": {
    "search": {
      "web": {
        "query": "*",
        "max_results": [1, 20]
      }
    }
  }
}
```

### 6. How the Lumon agent uses it

Once registered, the Lumon agent can call your plugin like any other function:

```
implement find.homes
  let results = search.web(query, 10)
  match results
    :ok(listings) -> return listings |> list.take(5)
    :error(msg) -> return :error("search failed: " + msg)
```

## Tips

- **One directory per namespace** — all `greet.*` functions go in `plugins/greet/`
- **Use tags** (`:ok`/`:error`) for functions that can fail — it lets the Lumon agent handle errors with `match`
- **Test scripts directly** with `echo '...' | python3` before wiring up the plugin
- **Check stderr** if a plugin call returns `:error` — your script's stderr becomes the error message
- **Read the Lumon spec** with `lumon spec` to understand the type system and language features
- **Contracts protect invariants** — use them to restrict URLs, numeric ranges, or enum values
