---
name: typecheck
description: Run pyright type checker. Use when wrapping up a task to catch type errors, or when debugging type-related issues.
allowed-tools: Bash
argument-hint: "[file-or-directory]"
---

Run pyright on the project.

If arguments are provided, check only those files:
```
.venv/bin/python -m pyright $ARGUMENTS
```

If no arguments are provided, check both the lumon package and tests:
```
.venv/bin/python -m pyright lumon/ tests/
```

After running:
1. Report the error/warning summary
2. For each error: show the file, line, and the pyright diagnostic
3. Do NOT attempt to fix anything — just report results
