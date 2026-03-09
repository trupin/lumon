# Lumon Agent Instructions

You are an agent operating inside Lumon, a safe interpreted language. You interact with the world through the `lumon` CLI and by directly editing files in the `sandbox/` directory. You cannot run arbitrary commands or use Python.

**IMPORTANT**: All `lumon` commands MUST use `--working-dir sandbox` to stay sandboxed inside the `sandbox/` directory. Never omit this flag. Exceptions: `lumon version`, `lumon spec`, and `lumon deploy .` work without `--working-dir`.

## Session startup

At the **start of every session**, check for Lumon updates using the `/auto-deploy` skill. This ensures you always have the latest agent configuration.

## Using plugins

**Before using any plugin for the first time in a session**, call its guide function to load usage guidelines:

```bash
lumon --working-dir sandbox 'return <namespace>.guide()'
```

For example, before using the browser plugin:
```bash
lumon --working-dir sandbox 'return browser.guide()'
```

The guide returns best practices, gotchas, and usage patterns specific to that plugin. Read it carefully — plugins often have non-obvious requirements (session management, rate limits, required call sequences) that the function signatures alone don't convey.

**How to check if a plugin has a guide**: run `lumon --working-dir sandbox browse <namespace>` and look for a `guide` function. Most plugins provide one.

## Versioning your work

**Commit after every significant unit of work** using the `/version-control` skill. Your code is your persistent memory — uncommitted work can be lost between sessions.

At minimum, commit when:
- A new function passes its tests
- A script completes a task end-to-end
- You fix a bug

Run `lumon --working-dir sandbox test` before every commit. Never commit broken code.

## What you cannot do

- Run arbitrary shell commands (only `lumon --working-dir sandbox` is available)
- Edit or create files outside the `sandbox/` directory
- Access Python, pip, or any other tooling
- Read files outside the current project directory
- Make HTTP POST requests or send authenticated requests
- Create or modify plugins (only a separate agent with elevated access can do this)

These restrictions are by design. Everything you need is available through Lumon primitives and direct file editing in `sandbox/`.

## Where to write code

All Lumon code MUST go in one of two places:

- **`sandbox/lumon/`** — Code to keep. Manifests go in `manifests/`, implementations in `impl/`, tests in `tests/`. This is the persistent codebase.
- **`sandbox/tmp/`** — Throwaway files: single-use scripts, respond payloads, intermediate data. **Delete every file here after use** — do not let them accumulate.

Do NOT write `.lumon` files anywhere else in `sandbox/` (no top-level scripts, no ad-hoc directories). Do NOT use inline CLI code for anything beyond quick one-off debugging.

## File cleanup

**Delete temporary files immediately after use.** The `sandbox/tmp/` directory is for transient files only — response payloads, one-off scripts, intermediate data. After a file has served its purpose (script ran, response sent), delete it:

```bash
lumon --working-dir sandbox 'io.delete("tmp/response.json")'
```

At the **start of each task**, clean up any leftover files from previous work:
- List and delete files in `sandbox/tmp/` using `io.list_dir` and `io.delete`

## CLI quick reference

| Command | What it does |
| :--- | :--- |
| `lumon version` | Print the installed Lumon version |
| `lumon spec` | Print the full language specification |
| `lumon deploy . --dry-run` | Show what agent config files would change |
| `lumon deploy . --force` | Update all agent config files to latest |
| `lumon --working-dir sandbox 'code'` | Run inline Lumon code |
| `lumon --working-dir sandbox file.lumon` | Run a `.lumon` file |
| `echo 'code' \| lumon --working-dir sandbox` | Run code from stdin |
| `lumon --working-dir sandbox browse` | List all namespaces |
| `lumon --working-dir sandbox browse <ns>` | Show function signatures for a namespace |
| `lumon --working-dir sandbox test` | Run all test files |
| `lumon --working-dir sandbox test <ns>` | Run tests for a specific namespace |
| `lumon --working-dir sandbox respond` | Resume a suspended `ask` or `spawn` (reads response files from `.lumon_comm/`) |

## Language quick reference

- **Bindings**: `let x = 42` (immutable, shadowing allowed)
- **Tags**: `:ok`, `:error("msg")` (like enums with payloads)
- **Match**: `match expr` with patterns, guards, destructuring
- **Pipes**: `items |> list.sort |> list.take(3)`
- **Lambdas**: `fn(x) -> x * 2` (multi-line with `let` bindings works everywhere, including as function arguments)
- **No loops**: use `list.map`, `list.filter`, `list.fold`
- **Nil-coalescing**: `value ?? "default"`
- **Types**: `text`, `number`, `bool`, `list<T>`, `map`, `tag`, `none`
