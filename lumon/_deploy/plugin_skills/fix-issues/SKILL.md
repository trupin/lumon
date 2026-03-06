---
name: fix-issues
description: Pull open issues from sandbox/PLUGIN_ISSUES.md and fix them by building or updating plugins. Marks each issue as fixed after working on it.
user-invocable: true
---

Read `../sandbox/PLUGIN_ISSUES.md`, find all issues with status `open`, and work through them one by one. For each issue, build or update the plugin, test it, then mark the issue as `fixed`.

## Phase 1: Read and triage

1. Read `../sandbox/PLUGIN_ISSUES.md`
2. Collect all issues with `**Status**: open`
3. If there are no open issues, report "No open plugin issues" and stop
4. List the open issues and their titles for visibility

## Phase 2: Fix each issue

For each open issue, in order:

### 2a. Understand the request

Read the issue carefully:
- **Description** — what capability is needed
- **Example** — the Lumon code the agent wishes it could write
- **Proposal** — how it could be implemented
- **Security considerations** — risks and mitigations to respect

The example code is your API contract — the plugin you build must make that exact code work (or as close as possible).

### 2b. Check existing state

Before building anything:
1. Read `../.lumon.json` to see what plugins already exist
2. Check if a plugin directory already exists for this namespace (`plugins/<namespace>/`)
3. If updating an existing plugin, read its current `manifest.lumon`, `impl.lumon`, and scripts

### 2c. Build or update the plugin

Follow the plugin creation protocol from `CLAUDE.md`:

1. **Create the plugin directory** if it doesn't exist: `plugins/<namespace>/`
2. **Write `manifest.lumon`** — define blocks matching the API from the issue's example code
3. **Write `impl.lumon`** — implement blocks using `plugin.exec`
4. **Write the script** — the actual executable that does the work
5. **Register in `../.lumon.json`** — add the plugin entry with appropriate contracts

When writing the script:
- Follow the `plugin.exec` protocol (JSON on stdin, JSON on stdout, stderr for errors)
- Respect the security considerations from the issue
- Apply contracts in `.lumon.json` to enforce any restrictions mentioned
- Use `:ok`/`:error` tags for functions that can fail
- Keep scripts under 30s execution time

### 2d. Test the plugin

1. **Test the script directly**: `echo '{"arg": "value"}' | python3 script.py`
2. **Test through the interpreter**: `lumon --working-dir ../sandbox 'return <namespace>.<function>(...)'`
3. Verify the output matches expectations

### 2e. Mark the issue as fixed

After the plugin works:

1. Edit `../sandbox/PLUGIN_ISSUES.md`
2. Change `**Status**: open` to `**Status**: fixed` for this issue
3. Add a **Resolution** note explaining what was built:

```markdown
- **Resolution**: Built `<namespace>` plugin with `<function>` in `plugins/<dir>/`. Registered in `.lumon.json` with contracts: <summary>.
```

Then move to the next open issue.

## Phase 3: Summary

After all issues are processed, report:
- How many issues were fixed
- What plugins were created or updated
- Any issues that could not be fixed (and why)

## Rules

- **One issue at a time.** Fix, test, mark as fixed, then move on. Don't batch.
- **Match the agent's API expectations.** The example code in the issue is what the Lumon agent expects to write — design your manifest to match it.
- **Respect security constraints.** If the issue says "read-only access", don't build write capabilities. Use contracts to enforce restrictions.
- **Don't modify the Lumon agent's code.** You work in `plugins/` and `../.lumon.json` only. Never edit files in `../sandbox/lumon/` — that's the Lumon agent's domain.
- **Only mark as fixed if it actually works.** If a test fails, debug and fix before marking.
- **Leave LUMON_ISSUES.md alone.** That file is for interpreter bugs — not your concern. Only touch `PLUGIN_ISSUES.md`.
