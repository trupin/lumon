---
name: auto-deploy
description: Detect when Lumon has been updated and deploy the new agent configuration. Run this at the start of every session.
---

## When to run

At the **start of every session**, before any other work. This ensures you're always running with the latest agent configuration.

## Step 1: Dry-run to see what changed

## IMPORTANT
**Do not** run lumon from within the sandbox. The deploy command should **always** run from the root.

```bash
lumon deploy . --dry-run
```

This lists:
- `+ file (new)` — new files that would be created
- `~ file` — existing files that differ from the bundled version

If the output says "Nothing to deploy — already up to date.", skip to Step 5.

## Step 2: Decide per file

For each file listed under "Would update":

1. **Read the current file** to check if it contains important user customizations
2. Decide whether to **keep** the current version or **accept the update**:
   - **Config files you customized** (e.g., files with project-specific content you added) → keep
   - **Managed files** (CLAUDE.md, settings.json, skills, hooks) → accept the update, these are maintained by Lumon and should stay in sync

Most of the time, all listed files should be updated — they're managed by Lumon and any changes are improvements or fixes.

## Step 3: Deploy

If you decided to accept all updates:

```bash
lumon deploy . --force
```

This overwrites all differing managed files. `.lumon.json` is never touched (it contains your plugin configuration).

## Step 4: Reload context

After deploying, read the updated files so the new instructions apply to this session:

1. Read `CLAUDE.md` — this is the main agent instruction file and may contain important changes
2. Read any skill files that were updated — they may contain new workflows or changed procedures

This ensures the current session benefits from the update, not just future sessions.
