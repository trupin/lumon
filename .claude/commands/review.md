---
description: Review recent implementation work for gaps, defects, missing tests, spec drift, and code quality issues. Run this after completing a task to catch problems before committing.
---

Review the implementation work done so far in this session. The goal is to produce a concrete, actionable list of problems to fix — not praise or commentary.

## 1. Gather context

Start by understanding what changed:

```
git diff main --stat
git diff main --name-only
```

Read every changed and newly created file in full. Also read `docs/spec.md` sections relevant to the changes.

## 2. Check each dimension

Work through each category below. For each problem found, note the file, line, and a one-sentence description.

### A. Spec compliance

- Compare the implementation against `docs/spec.md` line by line for the relevant sections
- Flag any behavior that diverges from the spec (missing edge case, wrong error type, different resolution order, etc.)
- Flag any spec requirement that has no corresponding test

### B. Test coverage gaps

- For each new function/method, check that there is at least one test exercising it
- Look for missing edge cases: empty inputs, error paths, boundary conditions, type mismatches
- Check that error messages are tested (not just error types)
- Verify negative tests exist (things that should fail do fail)

### C. Code quality

- Unused imports, dead code, unreachable branches
- Inconsistent patterns vs. the rest of the codebase (naming, error handling, DI style)
- Missing or wrong type annotations that would cause pyright issues
- Functions doing too much (should be split)
- Hardcoded values that should be constants or parameters

### D. Correctness risks

- Race conditions, resource leaks (unclosed files/processes)
- Error cases that silently swallow failures
- Cases where exceptions could escape without proper handling
- Off-by-one errors, wrong operator precedence
- Security issues (injection, path traversal, unbounded input)

### E. Integration gaps

- Does the change work with existing features? (pipes, closures, match, with/then/else, ask/spawn)
- Are existing tests still covering the right behavior after changes to shared code?
- Are there public API changes that aren't reflected in the CLI?

### F. Code coverage

- Run `.venv/bin/python -m coverage report --show-missing` (uses data from last `/test` run)
- Flag any changed files with coverage below 90%
- Flag any new functions/methods with 0% coverage

## 3. Produce the action list

Output a numbered list of **concrete actions**. Each action must be one of:

- **FIX**: A defect or incorrect behavior → describe what's wrong and what correct looks like
- **TEST**: A missing test → describe the test case (input, expected output)
- **COVERAGE**: A file or function with insufficient coverage → describe what's uncovered
- **SPEC**: A gap or ambiguity in the spec → describe what's unclear and suggest resolution
- **CLEAN**: A code quality issue → describe the problem and the fix

Format each action as:

```
N. [TYPE] file:line — Description
   → What to do
```

If there are no issues in a category, skip it — don't pad with non-issues.

## 4. Prioritize

Order the list by severity:
1. FIX items (correctness) first
2. TEST items (coverage gaps) second
3. COVERAGE items (low code coverage) third
4. SPEC items fourth
5. CLEAN items last

## Rules

- Do NOT fix anything — only report. The user will decide what to act on.
- Do NOT run tests, typecheck, or lint — those have their own skills.
- Be specific. "Improve error handling" is not actionable. "Handle FileNotFoundError in bridge.py:85 — currently crashes, should return LumonError" is.
- If $ARGUMENTS is provided, focus the review on that specific area.
