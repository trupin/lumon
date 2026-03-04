---
description: Run pytest and CLI bash tests with code coverage. Use when wrapping up a task to verify correctness and catch regressions. A task is not done unless its tests pass with no regressions.
allowed-tools: Bash
---

Run the full test suite for this project with code coverage measurement. There are two test suites:

## 0. Clean stale coverage data

Before running any tests, remove stale coverage files:
```
bash scripts/clean_coverage.sh
```

## 1. Pytest (interpreter unit tests)

If arguments are provided, run only those specific pytest tests:
```
.venv/bin/python -m pytest $ARGUMENTS -v --tb=short --cov=lumon --cov-report=term-missing
```

If no arguments are provided, run the full pytest suite:
```
.venv/bin/python -m pytest -v --tb=short --cov=lumon --cov-report=term-missing
```

## 2. CLI bash tests (always run when no arguments provided)

When no arguments are provided, also run the CLI integration tests with coverage enabled:
```
COVERAGE_PROCESS_START="$(pwd)/pyproject.toml" bash tests/test_cli.sh
```

## 3. Combine and report coverage

Only when no arguments were provided (i.e. both suites ran), combine parallel coverage data and show the report:
```
.venv/bin/python -m coverage combine 2>/dev/null; .venv/bin/python -m coverage report --show-missing
```

Skip this step when arguments were provided — pytest already printed the coverage report via `--cov-report=term-missing`.

## Reporting

After running:
1. Report the pass/fail summary for each suite separately
2. For any failures: show the test name, the assertion that failed, and the relevant code
3. If there are regressions (tests that were passing before but now fail), flag them clearly
4. Report the coverage summary (overall percentage and any files with low coverage)
5. Do NOT attempt to fix anything — just report results
