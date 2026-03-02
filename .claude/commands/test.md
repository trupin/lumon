---
description: Run pytest and CLI bash tests. Use when wrapping up a task to verify correctness and catch regressions. A task is not done unless its tests pass with no regressions.
allowed-tools: Bash
---

Run the full test suite for this project. There are two test suites:

## 1. Pytest (interpreter unit tests)

If arguments are provided, run only those specific pytest tests:
```
.venv/bin/python -m pytest $ARGUMENTS -v --tb=short
```

If no arguments are provided, run the full pytest suite:
```
.venv/bin/python -m pytest -v --tb=short
```

## 2. CLI bash tests (always run when no arguments provided)

When no arguments are provided, also run the CLI integration tests:
```
bash tests/test_cli.sh
```

## Reporting

After running:
1. Report the pass/fail summary for each suite separately
2. For any failures: show the test name, the assertion that failed, and the relevant code
3. If there are regressions (tests that were passing before but now fail), flag them clearly
4. Do NOT attempt to fix anything — just report results
