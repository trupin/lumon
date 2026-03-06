---
name: code-organization
description: How to organize Lumon code — file-first workflow, library structure, and refactoring discipline. Follow these conventions when writing any Lumon code.
---

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
