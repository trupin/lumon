---
name: review
description: Review completed work for learnings and improvements. Run this after finishing a task to reflect on code quality, reusability, ambiguity handling, and testing — then surface actionable issues.
user-invocable: true
---

After completing a task, run this review to extract learnings and surface improvements. The goal is to leave the codebase better than you found it — and to escalate what you can't fix yourself.

## Phase 0: Check for fixed issues

Before reviewing, read `sandbox/LUMON_ISSUES.md` and `sandbox/PLUGIN_ISSUES.md` (if it exists). Look for issues with `**Status**: fixed` — these have been resolved by the elevated agent since you last checked. For each fixed issue:

1. Read the `**Resolution**` field to understand what changed
2. Test the fix by running the `**Example**` code from the issue
3. If it works, change the status to `**Status**: closed` and add a `**Verified**` field confirming it works
4. If it doesn't work, change the status back to `**Status**: open` and add an `**Update**` field explaining what still fails

Do this before any other review work — fixed issues may affect what you find in the review.

## Phase 1: Gather what changed

Scan the files you touched during this task:

1. Read all `.lumon` files in `sandbox/lumon/manifests/`, `sandbox/lumon/impl/`, and `sandbox/scripts/` that you created or modified
2. Read any test files in `sandbox/lumon/tests/` related to the work
3. Note the `ask` and `spawn` interactions that occurred during script execution (from the conversation history)

## Phase 2: Evaluate each dimension

Work through each category below. For each issue found, note the file, function, and a one-sentence description.

### A. Code quality

- Functions longer than ~15 lines that should be split
- Hardcoded values that should be parameters
- Duplicated logic across functions that should be extracted into a shared helper
- Poor naming — function or parameter names that don't describe what they do
- Unnecessary complexity — simpler approaches that would work just as well

### B. Reusability

- Functions written for one task that could be generalized (e.g., `inbox.get_monday_items()` → `inbox.filter_by_day(items, day)`)
- Logic buried in scripts that should be promoted to the library layer
- Existing library functions that could have been reused but weren't (rediscovered after the fact)
- Namespaces that have grown too large and should be split

### C. Ambiguity handling (ask / spawn)

- Places where you hardcoded a decision that should use `ask` (the answer depends on context or judgment)
- Places where you used `ask` but could have used `spawn` (independent analysis, parallelizable)
- Places where you used `ask` unnecessarily (the answer is deterministic — no judgment needed)
- Missing `context` in `ask`/`spawn` calls — would providing more context produce better answers?
- Missing or vague `expects` — could the expected shape be more specific?

### D. Testing

- Functions with no tests
- Tests that only cover the happy path (missing error cases, edge cases, empty inputs)
- Tests that are too tightly coupled to implementation details
- Missing integration tests — the script works, but individual functions aren't tested in isolation

### E. Error handling

- Functions that don't handle `:error` tags from `io.*` or other fallible operations
- Silent failures — errors swallowed with `?? "default"` when they should propagate
- Missing match arms for error cases

### F. Optimizations

- Sequential `ask` calls that could be batched into a single `ask` with structured context
- Sequential operations on independent items that could use `spawn` for parallelism
- Redundant `io.read` calls — reading the same file multiple times when the result could be bound once

## Phase 3: Produce the improvement list

Output a numbered list grouped into two categories:

### Self-fixable (do these now)

Items you can fix yourself — code quality, reusability, testing, error handling within existing Lumon capabilities. For each item:

```
N. [TYPE] file — Description
   → What to do
```

Types: `REFACTOR`, `TEST`, `FIX`, `REUSE`

Apply these fixes immediately after listing them. Refactor the code, add the tests, fix the error handling. Then re-run tests to make sure nothing broke.

### Needs escalation (ask the user)

Items that require changes outside your sandbox — interpreter bugs, missing built-ins, new plugins. For each item:

```
N. [TYPE] Description
   → What's needed
   → Target: LUMON_ISSUES.md | PLUGIN_ISSUES.md
```

Types: `INTERPRETER`, `BUILTIN`, `PLUGIN`

**Do not file these automatically.** Present the list to the user and ask:

> "I found N items that need escalation. Which ones should I file as issues?"

Provide the full list with enough context for the user to decide. For each item the user approves:

1. Determine the correct file:
   - `INTERPRETER` and `BUILTIN` → `sandbox/LUMON_ISSUES.md`
   - `PLUGIN` → `sandbox/PLUGIN_ISSUES.md`
2. File the issue following the format from the `/issues` skill
3. Confirm what was filed

## Rules

- **Be concrete.** "Improve error handling" is not actionable. "Add `:error` match arm in `inbox.read` at line 5 — currently crashes on missing file" is.
- **Don't invent problems.** Only flag issues you actually observed during this task. Don't speculate about hypothetical edge cases you haven't encountered.
- **Fix what you can, escalate what you can't.** The split is simple: if it's Lumon code in `sandbox/`, fix it. If it's the interpreter, a built-in, or a missing plugin, escalate.
- **Keep it short.** A review with 3 actionable items is better than one with 15 nitpicks. Focus on what matters most.
