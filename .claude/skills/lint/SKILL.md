---
name: lint
description: Run pylint linter. Use when wrapping up a task to catch code quality issues, or when debugging lint-related problems.
allowed-tools: Bash
argument-hint: "[file-or-directory]"
---

Run pylint on the project.

If arguments are provided, check only those files:
```
.venv/bin/python -m pylint $ARGUMENTS
```

If no arguments are provided, check the lumon package:
```
.venv/bin/python -m pylint lumon/
```

After running:
1. Report the score and error/warning summary
2. For each issue: show the file, line, error code, and the pylint message
3. Do NOT attempt to fix anything — just report results
