#!/usr/bin/env bash
# CLI integration tests for the `lumon` command.
# Run from the project root: bash tests/test_cli.sh

set -euo pipefail

LUMON="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/lumon"
PASS=0
FAIL=0
TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() { echo "  PASS  $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL  $1"; echo "         expected: $2"; echo "         got:      $3"; FAIL=$((FAIL+1)); }

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        pass "$label"
    else
        fail "$label" "$expected" "$actual"
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        pass "$label"
    else
        fail "$label" "(contains) $needle" "$haystack"
    fi
}

run() { "$LUMON" "$@" 2>&1; }

# ---------------------------------------------------------------------------
# Inline code
# ---------------------------------------------------------------------------

assert_eq "inline: return number" \
    '{"type": "result", "value": 42}' \
    "$(run 'return 42')"

assert_eq "inline: return text" \
    '{"type": "result", "value": "hello"}' \
    "$(run 'return "hello"')"

assert_eq "inline: arithmetic" \
    '{"type": "result", "value": 10}' \
    "$(run 'return 2 + 3 * 2 + 2')"

assert_eq "inline: list" \
    '{"type": "result", "value": [1, 2, 3]}' \
    "$(run 'return [1, 2, 3]')"

assert_eq "inline: tag :ok" \
    '{"type": "result", "value": {"tag": "ok"}}' \
    "$(run 'return :ok')"

assert_eq "inline: tag with payload" \
    '{"type": "result", "value": {"tag": "error", "value": "oops"}}' \
    "$(run 'return :error("oops")')"

# ---------------------------------------------------------------------------
# Stdin
# ---------------------------------------------------------------------------

assert_eq "stdin: basic" \
    '{"type": "result", "value": 99}' \
    "$(echo 'return 99' | "$LUMON")"

assert_eq "stdin: let binding" \
    '{"type": "result", "value": 7}' \
    "$(printf 'let x = 3\nreturn x + 4' | "$LUMON")"

# ---------------------------------------------------------------------------
# File execution
# ---------------------------------------------------------------------------

TMPFILE="$TMPDIR_ROOT/test.lumon"
echo 'return "from file"' > "$TMPFILE"

assert_eq "file: .lumon extension" \
    '{"type": "result", "value": "from file"}' \
    "$(run "$TMPFILE")"

# ---------------------------------------------------------------------------
# Error output
# ---------------------------------------------------------------------------

assert_contains "error: undefined variable" \
    '"type": "error"' \
    "$(run 'return undefined_var')"

# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------

BROWSE_ROOT="$TMPDIR_ROOT/browse_project"
mkdir -p "$BROWSE_ROOT/lumon/manifests"

cat > "$BROWSE_ROOT/lumon/index.lumon" <<'EOF'
inbox -- message inbox management
io    -- filesystem operations
EOF

cat > "$BROWSE_ROOT/lumon/manifests/inbox.lumon" <<'EOF'
define inbox.read
  "Read all messages"
  returns: list<text> "The messages"
EOF

# Run browse from the project directory
assert_eq "browse: index" \
    "$(cat "$BROWSE_ROOT/lumon/index.lumon")" \
    "$(cd "$BROWSE_ROOT" && run browse)"

assert_eq "browse: namespace manifest" \
    "$(cat "$BROWSE_ROOT/lumon/manifests/inbox.lumon")" \
    "$(cd "$BROWSE_ROOT" && run browse inbox)"

assert_contains "browse: missing namespace returns error" \
    "error:" \
    "$(cd "$BROWSE_ROOT" && run browse nonexistent 2>&1 || true)"

assert_contains "browse: missing index returns error" \
    "error:" \
    "$(cd "$TMPDIR_ROOT" && run browse 2>&1 || true)"

# ---------------------------------------------------------------------------
# Test command
# ---------------------------------------------------------------------------

TEST_ROOT="$TMPDIR_ROOT/test_project"
mkdir -p "$TEST_ROOT/lumon/tests"

# A passing test file
cat > "$TEST_ROOT/lumon/tests/math.lumon" <<'EOF'
let x = 2 + 2
return x
EOF

# A failing test file (error)
cat > "$TEST_ROOT/lumon/tests/broken.lumon" <<'EOF'
return bad_var
EOF

assert_contains "test: passing file shows PASS" \
    "PASS" \
    "$(cd "$TEST_ROOT" && run test math)"

assert_contains "test: failing file shows FAIL" \
    "FAIL" \
    "$(cd "$TEST_ROOT" && run test broken 2>&1 || true)"

assert_contains "test: summary line" \
    "passed" \
    "$(cd "$TEST_ROOT" && run test 2>&1 || true)"

assert_contains "test: missing namespace reports skip" \
    "SKIP" \
    "$(cd "$TEST_ROOT" && run test nonexistent)"

# ---------------------------------------------------------------------------
# Respond (ask/spawn replay)
# ---------------------------------------------------------------------------

RESPOND_ROOT="$TMPDIR_ROOT/respond_project"
mkdir -p "$RESPOND_ROOT"

ASK_CODE='let choice = ask
  "Which item?"
return choice'

# First run: should produce an ask envelope and create state file
FIRST_OUT="$(cd "$RESPOND_ROOT" && run "$ASK_CODE")"
assert_contains "respond: first run produces ask" \
    '"type": "ask"' \
    "$FIRST_OUT"

assert_eq "respond: state file created" \
    "yes" \
    "$([ -f "$RESPOND_ROOT/.lumon_state.json" ] && echo yes || echo no)"

# Second run (respond): should produce a result
SECOND_OUT="$(cd "$RESPOND_ROOT" && run respond '"pay bill"')"
assert_eq "respond: result after response" \
    '{"type": "result", "value": "pay bill"}' \
    "$SECOND_OUT"

assert_eq "respond: state file cleared after result" \
    "no" \
    "$([ -f "$RESPOND_ROOT/.lumon_state.json" ] && echo yes || echo no)"

# Respond with no state should error
assert_contains "respond: no state → error" \
    "error:" \
    "$(cd "$RESPOND_ROOT" && run respond '42' 2>&1 || true)"

# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

assert_contains "spec: contains language title" \
    "Lumon Language Specification" \
    "$(run spec)"

assert_contains "spec: contains types section" \
    "## 1. Types" \
    "$(run spec)"

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

DEPLOY_ROOT="$TMPDIR_ROOT/deploy_target"
mkdir -p "$DEPLOY_ROOT"

run deploy "$DEPLOY_ROOT" > /dev/null 2>&1

assert_eq "deploy: CLAUDE.md at project root" \
    "yes" \
    "$([ -f "$DEPLOY_ROOT/CLAUDE.md" ] && echo yes || echo no)"

assert_eq "deploy: settings.json in .claude/" \
    "yes" \
    "$([ -f "$DEPLOY_ROOT/.claude/settings.json" ] && echo yes || echo no)"

assert_eq "deploy: CLAUDE.md NOT in .claude/" \
    "no" \
    "$([ -f "$DEPLOY_ROOT/.claude/CLAUDE.md" ] && echo yes || echo no)"

assert_eq "deploy: sandbox/ directory created" \
    "yes" \
    "$([ -d "$DEPLOY_ROOT/sandbox" ] && echo yes || echo no)"

# ---------------------------------------------------------------------------
# IO sandbox (--working-dir constrains io.read / io.write)
# ---------------------------------------------------------------------------

SANDBOX="$TMPDIR_ROOT/sandbox"
OUTSIDE="$TMPDIR_ROOT/outside"
mkdir -p "$SANDBOX" "$OUTSIDE"
echo "secret" > "$OUTSIDE/secret.txt"
echo "safe" > "$SANDBOX/safe.txt"

# Read inside working dir should succeed
assert_contains "sandbox: io.read inside working dir" \
    '"tag": "ok"' \
    "$(run --working-dir "$SANDBOX" 'return io.read("safe.txt")')"

# Read outside working dir via traversal should fail
assert_contains "sandbox: io.read traversal blocked" \
    '"tag": "error"' \
    "$(run --working-dir "$SANDBOX" 'return io.read("../outside/secret.txt")')"

# Write inside working dir should succeed
assert_contains "sandbox: io.write inside working dir" \
    '"tag": "ok"' \
    "$(run --working-dir "$SANDBOX" 'return io.write("new.txt", "hello")')"

# Write outside working dir via traversal should fail
assert_contains "sandbox: io.write traversal blocked" \
    '"tag": "error"' \
    "$(run --working-dir "$SANDBOX" 'return io.write("../outside/evil.txt", "pwned")')"

# Verify the outside file was not created
assert_eq "sandbox: evil file was not written" \
    "no" \
    "$([ -f "$OUTSIDE/evil.txt" ] && echo yes || echo no)"

# Read via absolute path outside working dir should fail
assert_contains "sandbox: io.read absolute path blocked" \
    '"tag": "error"' \
    "$(run --working-dir "$SANDBOX" "return io.read(\"$OUTSIDE/secret.txt\")")"

# ---------------------------------------------------------------------------
# --working-dir
# ---------------------------------------------------------------------------

WD_ROOT="$TMPDIR_ROOT/wd_project"
mkdir -p "$WD_ROOT/lumon/manifests"
cat > "$WD_ROOT/lumon/index.lumon" <<'EOF'
wd_test -- working dir test
EOF

assert_eq "working-dir: browse uses working dir" \
    "$(cat "$WD_ROOT/lumon/index.lumon")" \
    "$(run --working-dir "$WD_ROOT" browse)"

assert_eq "working-dir: inline code works with flag" \
    '{"type": "result", "value": 1}' \
    "$(run --working-dir "$WD_ROOT" 'return 1')"

# File path should resolve relative to working dir
WD_FILE_ROOT="$TMPDIR_ROOT/wd_file"
mkdir -p "$WD_FILE_ROOT"
echo 'return "from sandbox file"' > "$WD_FILE_ROOT/run.lumon"

assert_eq "working-dir: file path relative to working dir" \
    '{"type": "result", "value": "from sandbox file"}' \
    "$(run --working-dir "$WD_FILE_ROOT" run.lumon)"

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

assert_contains "version: prints version" \
    "lumon 0.1." \
    "$(run version)"

# ---------------------------------------------------------------------------
# Help flag
# ---------------------------------------------------------------------------

assert_contains "help: --help shows usage" \
    "lumon" \
    "$(run --help 2>&1 || true)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]]
