---
name: bump-version
description: Bump the Lumon version based on changes since the last version bump. Features bump minor, bug fixes bump patch.
allowed-tools: Bash, Read, Edit
---

Bump the version in `lumon/__init__.py` based on the nature of changes since the last bump.

## Steps

1. **Read the current version** from `lumon/__init__.py` (`__version__ = "X.Y.Z"`).

2. **Find the last version bump commit:**
   ```bash
   git log --oneline --diff-filter=M -- lumon/__init__.py | head -1
   ```
   This gives the most recent commit that modified the version file. Use its hash as the baseline.

3. **List commits since the last bump:**
   ```bash
   git log --oneline <last-bump-hash>..HEAD
   ```
   If there are no commits since the last bump, report "nothing to bump" and stop.

4. **Classify the changes** by reading the commit messages:
   - **Feature** — commit message starts with "Add", "Implement", "Support", "Enable", or introduces new functionality
   - **Fix** — commit message starts with "Fix", "Correct", "Patch", "Handle", or resolves a bug
   - Other commits (refactor, docs, tests, chore) don't influence the bump level but are included in the release

5. **Determine the bump level:**
   - If ANY commit is a feature → bump **minor** (X.Y+1.0)
   - If ALL commits are fixes (or non-functional changes) → bump **patch** (X.Y.Z+1)

6. **Apply the bump** — edit `lumon/__init__.py`, changing the `__version__` string to the new version.

7. **Report** the old version, new version, bump level, and the list of commits included.

8. **Commit the bump:**
   ```bash
   git add lumon/__init__.py
   git commit -m "$(cat <<'EOF'
   Bump version X.Y.Z → A.B.C

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   EOF
   )"
   ```
   Replace the version numbers in the message with the actual old and new versions.
