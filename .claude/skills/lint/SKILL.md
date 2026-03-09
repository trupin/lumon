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

## Fixing lint issues

When fixing lint issues (outside of this skill), **never suppress warnings with `# pylint: disable=...` comments** unless there is genuinely no other solution. The correct fix is to refactor the code to satisfy the linter.

Examples of **wrong** fixes:
- Adding `# pylint: disable=too-many-lines` instead of splitting a large module
- Adding `# pylint: disable=too-many-arguments` instead of grouping parameters
- Adding `# pylint: disable=import-outside-toplevel` instead of moving the import to the top of the file

A `disable` comment is acceptable **only** when:
- The linter is provably wrong (e.g., `invalid-name` on a mutable module-level variable that pylint mistakes for a constant)
- Fixing the issue would make the code materially worse or is impossible given the design constraints
- You can articulate a clear reason — add it as a brief comment next to the disable
