---
description: Install lumon globally as a standalone CLI tool and verify it works.
allowed-tools: Bash
---

Install lumon globally using `uv tool install` and verify the installation:

1. **Install** (force rebuild to pick up latest code):
```
uv tool install . --reinstall
```

2. **Verify version matches source**:
   - Read the expected version from `lumon/__init__.py` (`__version__`)
   - Run `lumon version` and check the output matches
   - If they don't match, report the mismatch and fail

3. **Smoke test** — run a quick sanity check:
```
lumon 'return 1 + 1'
```
   - Verify the output is `{"type": "result", "value": 2}`

4. **Report** the installed version and confirm everything is working.
