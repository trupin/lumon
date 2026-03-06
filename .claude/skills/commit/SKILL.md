---
name: commit
description: Commit current changes. One commit per significant task. Never commit directly to main/master — create a feature branch first if not already on one.
allowed-tools: Bash
argument-hint: "[commit-message-guidance]"
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

5. **Staging rules — read carefully:**
   - Use `git add -u` to stage all tracked changes (modifications + deletions). This is safe and handles deleted files correctly.
   - Then `git add <path>` for any new untracked files you want to include.
   - Never use `git add` on deleted files by name — it will fail. Use `git add -u` instead.
   - Include `.claude/skills/` changes when relevant (skills are project config).
   - Exclude secrets, build artifacts, and unrelated changes.

6. **If `git commit` fails with `index.lock` exists**, wait a moment and retry once. If it still fails, report the error.

7. **After committing**, push to the remote with `git push`. Never use `--force` or `--force-with-lease`. Report what was committed and pushed, including the branch name.

If $ARGUMENTS is provided, use it as guidance for the commit message.
