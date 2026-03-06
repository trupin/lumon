---
name: fix-issues
description: Read LUMON_ISSUES.md from the lumon-test sandbox, plan fixes for open issues, implement them, then mark them as fixed.
---

Fix open issues listed in the Lumon agent's issue file. Follow these steps exactly:

## 1. Read the issues file

Read the file at `/Users/theophanerupin/code/lumon-test/sandbox/LUMON_ISSUES.md`. This file tracks interpreter bugs and language gaps filed by the Lumon agent.

Each issue is a `## Title` section with structured fields:
- **Status**: `open`, `fixed`, or `closed`
- **Description**: what's wrong
- **Example**: Lumon code that demonstrates the problem
- **Expected**: what should happen
- **Got**: what actually happens

## 2. Identify open issues

An issue is **open** if its `**Status**` field is `open`. Collect all open issues.

If there are no open issues, report "No open issues found" and stop.

## 3. Plan fixes

For each open issue, enter plan mode and design an implementation plan:
- Read the spec (`docs/spec.md`) and relevant source files to understand the gap
- Run the example code from the issue to reproduce the problem
- Identify which files need to change and what the fix looks like
- Present the plan for user approval before implementing

Work through issues one at a time in order. Do NOT batch them.

## 4. Implement and verify each fix

After the user approves a plan:
1. Implement the fix
2. Run `/test` to verify no regressions
3. Run `/typecheck` on modified files
4. Run `/commit` to commit the fix

## 5. Mark the issue as fixed

After a fix is committed, update the issues file at `/Users/theophanerupin/code/lumon-test/sandbox/LUMON_ISSUES.md`:
- Change `**Status**: open` to `**Status**: fixed` for that issue
- Add a `**Resolution**` field explaining what was fixed
- Do NOT modify any other content in the section

## 6. Continue to next issue

Repeat steps 3–5 for each remaining open issue. After all issues are fixed, report a summary of what was done.
