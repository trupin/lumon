---
description: Run pytest. Use when wrapping up a task to verify correctness and catch regressions. A task is not done unless its tests pass with no regressions.
allowed-tools: Bash
---

Run the test suite for this project.

If arguments are provided, run only those specific tests:
```
.venv/bin/python -m pytest $ARGUMENTS -v --tb=short
```

If no arguments are provided, run the full suite:
```
.venv/bin/python -m pytest -v --tb=short
```

After running:
1. Report the pass/fail summary
2. For any failures: show the test name, the assertion that failed, and the relevant code
3. If there are regressions (tests that were passing before but now fail), flag them clearly
4. Do NOT attempt to fix anything — just report results
