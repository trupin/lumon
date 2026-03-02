---
description: Commit current changes. One commit per significant task. Never commit directly to main/master — create a feature branch first if not already on one.
allowed-tools: Bash
---

Commit the current changes following these rules:

1. **Never commit to main/master.** If on main/master, create a feature branch first with a descriptive name (e.g., `feat/add-parser`, `fix/type-checker-unions`).

2. **One commit per significant task.** Each commit should represent a coherent unit of work. Don't bundle unrelated changes.

3. **Before committing:**
   - Run `git status` and `git diff --stat` to understand what changed
   - Run `git log --oneline -5` to match the repo's commit style

4. **Commit message format:**
   - Short imperative subject line (≤ 72 chars)
   - Focus on the "why", not the "what"
   - End with: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

5. **Stage only relevant files.** Don't `git add -A` blindly — exclude secrets, build artifacts, and unrelated changes.

6. **After committing**, report what was committed and the branch name.

If $ARGUMENTS is provided, use it as guidance for the commit message.
