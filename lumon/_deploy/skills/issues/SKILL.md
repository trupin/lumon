---
name: issues
description: How to track issues across two files — LUMON_ISSUES.md for interpreter/language bugs and PLUGIN_ISSUES.md for missing external capabilities. Covers the full lifecycle of opening, verifying, and closing issues.
user-invocable: false
---

## Issue tracking

You maintain two issue files in the `sandbox/` directory:

| File | What goes in it |
| :--- | :--- |
| `sandbox/LUMON_ISSUES.md` | Interpreter bugs, language gaps, broken built-ins, wrong type signatures — anything wrong with Lumon itself |
| `sandbox/PLUGIN_ISSUES.md` | Missing external capabilities — APIs, system tools, scripts that require a plugin to be built by an elevated agent |

Each file is self-documenting — it starts with a header template that explains the format and lifecycle. If a file doesn't exist yet, create it with the appropriate template below.

## Issue lifecycle

Issues move through three statuses: **open → fixed → closed** (or back to **open** if the fix doesn't work).

Three agents are involved:

1. **You (Lumon agent)** — open issues when you hit a blocker, verify fixes, close or reopen
2. **Elevated agent** — reads your issues, implements fixes, marks them as `fixed`
3. **You again** — test the fix, then `closed` if it works or `open` with an update if it doesn't

### Opening an issue

When you encounter a blocker:

1. Determine the correct file — interpreter/language problem → `LUMON_ISSUES.md`, missing plugin → `PLUGIN_ISSUES.md`
2. Append a new issue **at the end** of the file (before any `closed` issues)
3. Set status to `open`
4. Always include a **Lumon code example** that demonstrates the problem

### Verifying a fix

At the start of each session, check both issue files for issues marked `fixed`:

1. Read the issue and its resolution
2. Write a small test — run the Lumon code from the example and verify it works
3. If it works → change status to `closed`, add a **Verified** note
4. If it doesn't → change status back to `open`, add an **Update** explaining what still fails

### Never delete issues

Issues are an audit trail. Don't remove them — closed issues stay in the file as a record.

## LUMON_ISSUES.md template

If `sandbox/LUMON_ISSUES.md` doesn't exist, create it with this content:

```markdown
# Lumon Issues

<!-- Issue tracker for Lumon interpreter bugs and language gaps.
     This file is maintained by the Lumon agent.

     Lifecycle: open → fixed (by elevated agent) → closed (by Lumon agent after verification)
     If a fix doesn't work, reopen with an update.

     Format:
     ## [SHORT-TITLE]
     - **Status**: open | fixed | closed
     - **Description**: What's wrong
     - **Example**: Lumon code that demonstrates the problem
     - **Expected**: What should happen
     - **Got**: What actually happens
     - **Update**: (optional) Added when reopening — what still fails
     - **Verified**: (optional) Added when closing — confirmation it works
-->
```

### When to write a Lumon issue

- A built-in function behaves differently than its signature or the spec says
- A type error is raised incorrectly, or a real type error is missed
- The parser rejects valid Lumon code or accepts invalid code
- A `define` signature is missing a parameter or return type you need
- Any interpreter behavior that blocks your work and you cannot work around

### Example Lumon issue

```markdown
## text.split rejects second argument

- **Status**: open
- **Description**: `text.split` should accept a delimiter argument but errors when one is provided
- **Example**:
  ```lumon
  let result = text.split("a,b,c", ",")
  return list.length(result)
  ```
- **Expected**: `{"type": "result", "value": 3}`
- **Got**: `{"type": "error", "message": "text.split: expected 1 argument, got 2"}`
```

## PLUGIN_ISSUES.md template

If `sandbox/PLUGIN_ISSUES.md` doesn't exist, create it with this content:

```markdown
# Plugin Issues

<!-- Issue tracker for missing external capabilities that require a plugin.
     This file is maintained by the Lumon agent.

     Lifecycle: open → fixed (by elevated agent who builds the plugin) → closed (by Lumon agent after verification)
     If a fix doesn't work, reopen with an update.

     Format:
     ## [SHORT-TITLE]
     - **Status**: open | fixed | closed
     - **Description**: What capability is needed and why
     - **Example**: Lumon code you wish you could write
     - **Proposal**: How it could be implemented
     - **Security considerations**: Risks and mitigations
     - **Update**: (optional) Added when reopening — what still fails
     - **Verified**: (optional) Added when closing — confirmation it works
-->
```

### When to write a plugin issue

- A task needs an external API, system command, or tool that no current namespace provides
- You need to send data to or receive data from an external service
- You need a capability that is fundamentally outside the Lumon sandbox (network, filesystem beyond sandbox, etc.)

### Example plugin issue

```markdown
## Slack messaging

- **Status**: open
- **Description**: Need to send messages to Slack channels for deployment notifications
- **Example**:
  ```lumon
  let response = slack.send("general", "Deployment complete")
  match response
    :ok(_) -> return "sent"
    :error(m) -> return "failed: " + m
  ```
  This code cannot run because no `slack` namespace exists.
- **Proposal**: A `slack` plugin with a `slack.send(channel, message)` function using the Slack API
- **Security considerations**: Requires a scoped bot token (chat:write only). The contract should restrict `channel` to an allowlist of approved channels. No reading of messages needed — write-only access.
```

## Session startup checklist

Every session, before starting new work:

1. Read `sandbox/LUMON_ISSUES.md` — check for any `fixed` issues to verify
2. Read `sandbox/PLUGIN_ISSUES.md` — check for any `fixed` issues to verify
3. Verify each `fixed` issue (test the example code)
4. Close or reopen based on results
5. Check if any previously blocked work can now proceed
