---
name: pr
description: Open a pull request for the current branch. One PR per session — summarizes all commits on the branch.
allowed-tools: Bash
argument-hint: "[title-guidance]"
---

Open a pull request for the current session's work:

1. **Check state:**
   - Verify we're NOT on main/master (abort if so)
   - Run `git log main..HEAD --oneline` to see all commits in this branch
   - Run `git diff main...HEAD --stat` to see overall changes
   - Check if remote branch exists and is up to date

2. **Push if needed:** `git push -u origin HEAD`

3. **Create the PR** using `gh pr create`:
   - Title: short summary of the session's work (≤ 70 chars)
   - Body format:
     ```
     ## Summary
     <1-3 bullet points covering what was done>

     ## Test plan
     - [ ] All new tests pass
     - [ ] No test regressions
     - [ ] Pyright clean

     🤖 Generated with [Claude Code](https://claude.com/claude-code)
     ```

4. **Report** the PR URL when done.

If $ARGUMENTS is provided, use it as guidance for the PR title/description.
