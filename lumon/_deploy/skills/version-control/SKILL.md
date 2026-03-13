---
name: version-control
description: How to version your work using git. Commit after every significant task, use branches for experiments, and tag stable milestones. Follow this skill whenever you complete meaningful work.
---

## Important: git operates on the project root

Git commands always run from the **project root** (one level above the sandbox), not from within the sandbox. This means:

- `git.status()` shows changes across the entire project
- `git.add(path)` paths are **relative to the project root** — use `"sandbox/lumon/manifests/inbox.lumon"`, not `"lumon/manifests/inbox.lumon"`
- `git.diff()` and `git.log()` reflect the full project history

## When to commit

**Commit after every significant unit of work.** A significant unit is:

- A new library function (manifest + impl + test all passing)
- A bug fix to an existing function
- A new script that completes a task
- A refactoring that changes code organization

Do NOT commit broken code. Run `lumon --working-dir sandbox test` before committing.

## How to commit

### 1. Check what changed

```bash
lumon --working-dir sandbox 'return git.status()'
lumon --working-dir sandbox 'return git.diff()'
```

Review the changes. Make sure only intentional changes are present.

### 2. Stage files

**Preferred: stage all tracked changes at once:**

```bash
lumon --working-dir sandbox 'return git.add_all()'
```

This stages all modified and deleted tracked files. Use this for the common case where you've reviewed `git.diff()` and want to commit everything.

**Selective staging** — when you need to commit only some changes, stage individual files (paths relative to the **project root**):

```bash
lumon --working-dir sandbox 'return git.add("sandbox/lumon/manifests/inbox.lumon")'
lumon --working-dir sandbox 'return git.add("sandbox/lumon/impl/inbox.lumon")'
lumon --working-dir sandbox 'return git.add("sandbox/lumon/tests/inbox.lumon")'
```

### 3. Verify what's staged

```bash
lumon --working-dir sandbox 'return git.diff_staged()'
```

### 4. Commit with a clear message

```bash
lumon --working-dir sandbox 'return git.commit("Add inbox.read: extract list items from markdown")'
```

The commit returns the short hash. Log it mentally — you can reference it later.

### Commit message format

Write messages that describe **what** and **why**, not how:

- `"Add inbox.categorize: classify items using spawn"` — new function
- `"Fix inbox.read: handle empty files without crashing"` — bug fix
- `"Refactor utils: extract text helpers from inbox"` — refactoring

Keep messages under 72 characters. Start with a verb: Add, Fix, Refactor, Update, Remove.

## How to use branches

Use branches to experiment without risking stable code.

### Create and switch to a branch

```bash
lumon --working-dir sandbox 'return git.branch("experiment/parallel-categorize")'
lumon --working-dir sandbox 'return git.checkout("experiment/parallel-categorize")'
```

### List branches

```bash
lumon --working-dir sandbox 'return git.branch_list()'
```

### Return to main when done

```bash
lumon --working-dir sandbox 'return git.checkout("main")'
```

### When to branch

- **Trying a different approach** to an existing function
- **Large refactors** that touch multiple namespaces
- **Risky changes** you might want to abandon

For routine work (new functions, small fixes), commit directly — no branch needed.

## How to tag milestones

Tag stable points you might want to return to:

```bash
lumon --working-dir sandbox 'return git.tag("v1-inbox-working")'
```

Good moments to tag:

- All tests pass for a namespace
- A complex script works end-to-end
- Before a large refactor

### List tags

```bash
lumon --working-dir sandbox 'return git.tag_list()'
```

## How to review history

### Recent commits

```bash
lumon --working-dir sandbox 'return git.log(10)'
```

### Commit details

```bash
lumon --working-dir sandbox 'return git.show("HEAD")'
lumon --working-dir sandbox 'return git.show("abc1234")'
```

## How to undo a staging mistake

If you staged the wrong file (paths relative to project root):

```bash
lumon --working-dir sandbox 'return git.reset("sandbox/tmp/scratch.lumon")'
```

This unstages the file but keeps your changes in the working tree.

## Workflow summary

```
1. Write code (manifests, impls, tests)
2. Test:   lumon --working-dir sandbox test <ns>
3. Review: git.status() → git.diff()
4. Stage:  git.add_all() or git.add("sandbox/path/to/file") per file
5. Commit: git.commit("Clear message")
6. Repeat
```

## Rules

- **Never commit without testing first.** Run tests, confirm they pass, then commit.
- **Never stage temporary files.** Files in `sandbox/tmp/` should never be committed.
- **One logical change per commit.** Don't mix unrelated changes.
- **Commit messages must be meaningful.** "Update code" is not acceptable.
- **Branch for experiments, commit for progress.** If you're unsure whether a change is good, branch first.
- **Paths are project-root-relative.** Always prefix sandbox paths with `sandbox/` when staging or resetting.
