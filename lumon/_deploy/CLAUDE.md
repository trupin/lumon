# Lumon Agent Instructions

You are an agent operating inside Lumon, a safe interpreted language. You interact with the world through the `lumon` CLI and by directly editing files in the `sandbox/` directory. You cannot run arbitrary commands or use Python.

**IMPORTANT**: All `lumon` commands MUST use `--working-dir sandbox` to stay sandboxed inside the `sandbox/` directory. Never omit this flag.

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
