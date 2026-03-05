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
# Long inline code (issue #12 — no OSError on strings exceeding path limit)
# ---------------------------------------------------------------------------

LONG_CODE="return 1 + $(python3 -c "print(' + '.join(['1'] * 300))")"
assert_eq "inline: long string no OSError" \
    '{"type": "result", "value": 301}' \
    "$(run "$LONG_CODE")"

# Code with newlines should be treated as inline, not a file path
assert_eq "inline: multiline string" \
    '{"type": "result", "value": 3}' \
    "$(run "$(printf 'let x = 1\nlet y = 2\nreturn x + y')")"

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
assert_contains "browse: index includes user namespaces" \
    "inbox" \
    "$(cd "$BROWSE_ROOT" && run browse)"

assert_eq "browse: namespace manifest" \
    "$(cat "$BROWSE_ROOT/lumon/manifests/inbox.lumon")" \
    "$(cd "$BROWSE_ROOT" && run browse inbox)"

assert_contains "browse: missing namespace returns error" \
    "error:" \
    "$(cd "$BROWSE_ROOT" && run browse nonexistent 2>&1 || true)"

# ---------------------------------------------------------------------------
# Browse: built-in namespaces (bundled manifests)
# ---------------------------------------------------------------------------

assert_contains "browse: built-in namespace io" \
    "io.read" \
    "$(run browse io)"

assert_contains "browse: built-in namespace text" \
    "text.split" \
    "$(run browse text)"

assert_contains "browse: built-in namespace list" \
    "list.map" \
    "$(run browse list)"

assert_contains "browse: built-in namespace map" \
    "map.get" \
    "$(run browse map)"

assert_contains "browse: built-in namespace number" \
    "number.round" \
    "$(run browse number)"

assert_contains "browse: built-in namespace type" \
    "type.of" \
    "$(run browse type)"

assert_contains "browse: built-in namespace http" \
    "http.get" \
    "$(run browse http)"

assert_contains "browse: built-in namespace git" \
    "git.status" \
    "$(run browse git)"

assert_contains "browse: built-in namespace time" \
    "time.now" \
    "$(run browse time)"

# Index includes built-in namespaces even without lumon/index.lumon on disk
assert_contains "browse: index includes built-in io" \
    "io" \
    "$(run browse)"

assert_contains "browse: index includes built-in text" \
    "text" \
    "$(run browse)"

assert_contains "browse: index includes built-in git" \
    "git" \
    "$(run browse)"

# Index merges built-in and user namespaces
assert_contains "browse: index includes user namespace from disk" \
    "inbox" \
    "$(cd "$BROWSE_ROOT" && run browse)"

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

assert_eq "deploy: sandbox-guard hook deployed" \
    "yes" \
    "$([ -f "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" ] && echo yes || echo no)"

# Verify the hook blocks non-lumon commands
assert_contains "deploy: hook blocks bad commands" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

# Verify the hook allows lumon sandbox commands
assert_eq "deploy: hook allows sandbox commands" \
    "" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon --working-dir sandbox browse"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

assert_contains "deploy: hook blocks chained commands" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon --working-dir sandbox browse && echo pwned"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

assert_contains "deploy: hook blocks piped to unsafe commands" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon --working-dir sandbox browse | bash"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

# Hook allows piping to safe read-only commands
assert_eq "deploy: hook allows pipe to head" \
    "" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon spec | head -200"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

assert_eq "deploy: hook allows pipe to grep" \
    "" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon --working-dir sandbox browse | grep inbox"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

assert_eq "deploy: hook allows 2>&1 with pipe" \
    "" \
    "$(echo '{"tool_name": "Bash", "tool_input": {"command": "lumon spec 2>&1 | head -200"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

# Hook allows lumon code containing |> and -> inside quotes
assert_eq "deploy: hook allows lumon code with pipes and arrows" \
    "" \
    "$(printf '{"tool_name": "Bash", "tool_input": {"command": "lumon --working-dir sandbox '"'"'return [1,2,3] |> list.map(fn(x) -> x * 2)'"'"'"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

# Edit hook: allowed inside sandbox
assert_eq "deploy: hook allows Edit in sandbox" \
    "" \
    "$(echo '{"tool_name": "Edit", "tool_input": {"file_path": "sandbox/foo.lumon"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

# Edit hook: blocked outside sandbox
assert_contains "deploy: hook blocks Edit outside sandbox" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Edit", "tool_input": {"file_path": "CLAUDE.md"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

# Edit hook: blocked traversal out of sandbox
assert_contains "deploy: hook blocks Edit traversal" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Edit", "tool_input": {"file_path": "sandbox/../secret.txt"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

# Read hook: allowed inside current directory
assert_eq "deploy: hook allows Read in current dir" \
    "" \
    "$(echo '{"tool_name": "Read", "tool_input": {"file_path": "CLAUDE.md"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

assert_eq "deploy: hook allows Read in sandbox subdir" \
    "" \
    "$(echo '{"tool_name": "Read", "tool_input": {"file_path": "sandbox/foo.lumon"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1)"

# Read hook: blocked outside current directory
assert_contains "deploy: hook blocks Read outside current dir" \
    "BLOCKED" \
    "$(echo '{"tool_name": "Read", "tool_input": {"file_path": "../outside/secret.txt"}}' | python3 "$DEPLOY_ROOT/.claude/hooks/sandbox-guard.py" 2>&1 || true)"

# Deploy: plugins directory
assert_eq "deploy: plugins/ directory created" \
    "yes" \
    "$([ -d "$DEPLOY_ROOT/plugins" ] && echo yes || echo no)"

assert_eq "deploy: plugins/CLAUDE.md deployed" \
    "yes" \
    "$([ -f "$DEPLOY_ROOT/plugins/CLAUDE.md" ] && echo yes || echo no)"

assert_contains "deploy: plugins CLAUDE.md has protocol section" \
    "plugin.exec" \
    "$(cat "$DEPLOY_ROOT/plugins/CLAUDE.md")"

assert_contains "deploy: plugins CLAUDE.md has directory structure" \
    "manifest.lumon" \
    "$(cat "$DEPLOY_ROOT/plugins/CLAUDE.md")"

assert_eq "deploy: .lumon.json created at root" \
    "yes" \
    "$([ -f "$DEPLOY_ROOT/.lumon.json" ] && echo yes || echo no)"

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

assert_contains "working-dir: browse uses working dir" \
    "wd_test" \
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
# Plugin system (real subprocess)
# ---------------------------------------------------------------------------

PLUGIN_ROOT="$TMPDIR_ROOT/plugin_project"
mkdir -p "$PLUGIN_ROOT/sandbox/lumon/manifests" "$PLUGIN_ROOT/plugins/ext"

# Plugin manifest
cat > "$PLUGIN_ROOT/plugins/ext/manifest.lumon" <<'EOF'
define ext.greet
  "Greet someone"
  takes:
    name: text "Name"
  returns: text "Greeting"
EOF

# Plugin impl using plugin.exec
cat > "$PLUGIN_ROOT/plugins/ext/impl.lumon" <<'EOF'
implement ext.greet
  let result = plugin.exec("python3 greet.py", {name: name})
  return result
EOF

# A working plugin script
cat > "$PLUGIN_ROOT/plugins/ext/greet.py" <<'PYEOF'
import json, sys
args = json.load(sys.stdin)
name = args["name"]
json.dump(f"Hello, {name}!", sys.stdout)
PYEOF

# .lumon.json at project root
cat > "$PLUGIN_ROOT/.lumon.json" <<'EOF'
{"plugins": {"ext": {}}}
EOF

# Test: plugin call with real subprocess
assert_eq "plugin: real subprocess returns value" \
    '{"type": "result", "value": "Hello, World!"}' \
    "$(run --working-dir "$PLUGIN_ROOT/sandbox" 'return ext.greet("World")')"

# Test: non-zero exit returns :error(stderr)
PLUGIN_FAIL_ROOT="$TMPDIR_ROOT/plugin_fail"
mkdir -p "$PLUGIN_FAIL_ROOT/sandbox/lumon" "$PLUGIN_FAIL_ROOT/plugins/ext"
cp "$PLUGIN_ROOT/plugins/ext/manifest.lumon" "$PLUGIN_FAIL_ROOT/plugins/ext/manifest.lumon"
cat > "$PLUGIN_FAIL_ROOT/plugins/ext/impl.lumon" <<'EOF'
implement ext.greet
  let result = plugin.exec("python3 fail.py", {name: name})
  return result
EOF
cat > "$PLUGIN_FAIL_ROOT/plugins/ext/fail.py" <<'PYEOF'
import sys
print("something went wrong", file=sys.stderr)
sys.exit(1)
PYEOF
cat > "$PLUGIN_FAIL_ROOT/.lumon.json" <<'EOF'
{"plugins": {"ext": {}}}
EOF

assert_contains "plugin: non-zero exit returns :error" \
    '"tag": "error"' \
    "$(run --working-dir "$PLUGIN_FAIL_ROOT/sandbox" 'return ext.greet("test")')"

# Test: browse shows plugin namespaces
assert_contains "plugin: browse shows plugin namespace" \
    "ext" \
    "$(cd "$PLUGIN_ROOT/sandbox" && run browse)"

# Test: browse shows plugin manifest
assert_contains "plugin: browse shows plugin manifest" \
    "ext.greet" \
    "$(cd "$PLUGIN_ROOT/sandbox" && run browse ext)"

# Test: contract violation → interpreter error
PLUGIN_CONTRACT_ROOT="$TMPDIR_ROOT/plugin_contract"
mkdir -p "$PLUGIN_CONTRACT_ROOT/sandbox/lumon" "$PLUGIN_CONTRACT_ROOT/plugins/web"

cat > "$PLUGIN_CONTRACT_ROOT/plugins/web/manifest.lumon" <<'EOF'
define web.search
  "Search"
  takes:
    url: text "URL"
  returns: text "Results"
EOF
cat > "$PLUGIN_CONTRACT_ROOT/plugins/web/impl.lumon" <<'EOF'
implement web.search
  let result = plugin.exec("echo ok", {url: url})
  return result
EOF
cat > "$PLUGIN_CONTRACT_ROOT/.lumon.json" <<'EOF'
{"plugins": {"web": {"search": {"url": "https://zillow.com/*"}}}}
EOF

assert_contains "plugin: contract violation returns error" \
    '"type": "error"' \
    "$(run --working-dir "$PLUGIN_CONTRACT_ROOT/sandbox" 'return web.search("https://redfin.com")')"

# Test: unlisted plugin not accessible
PLUGIN_UNLISTED_ROOT="$TMPDIR_ROOT/plugin_unlisted"
mkdir -p "$PLUGIN_UNLISTED_ROOT/sandbox/lumon" "$PLUGIN_UNLISTED_ROOT/plugins/secret"
cat > "$PLUGIN_UNLISTED_ROOT/plugins/secret/manifest.lumon" <<'EOF'
define secret.fn
  "Secret"
  returns: text
EOF
cat > "$PLUGIN_UNLISTED_ROOT/plugins/secret/impl.lumon" <<'EOF'
implement secret.fn
  return "nope"
EOF
cat > "$PLUGIN_UNLISTED_ROOT/.lumon.json" <<'EOF'
{"plugins": {}}
EOF

assert_contains "plugin: unlisted plugin not accessible" \
    '"type": "error"' \
    "$(run --working-dir "$PLUGIN_UNLISTED_ROOT/sandbox" 'return secret.fn()')"

# ---------------------------------------------------------------------------
# Multi-instance plugins
# ---------------------------------------------------------------------------

MULTI_ROOT="$TMPDIR_ROOT/multi_project"
mkdir -p "$MULTI_ROOT/sandbox/lumon/manifests" "$MULTI_ROOT/plugins/browser"

# Plugin manifest (source namespace: browser)
cat > "$MULTI_ROOT/plugins/browser/manifest.lumon" <<'EOF'
define browser.search
  "Search the web"
  takes:
    url: text "URL to search"
    max_results: number "Max results" = 10
  returns: text "Results"
EOF

# Plugin impl
cat > "$MULTI_ROOT/plugins/browser/impl.lumon" <<'EOF'
implement browser.search
  let result = plugin.exec("python3 search.py", {url: url, max_results: max_results})
  return result
EOF

# Plugin script that returns instance name + url
cat > "$MULTI_ROOT/plugins/browser/search.py" <<'PYEOF'
import json, sys, os
args = json.load(sys.stdin)
instance = os.environ.get("LUMON_PLUGIN_INSTANCE", "unknown")
json.dump(f"{instance}:{args['url']}", sys.stdout)
PYEOF

# Multi-instance config
cat > "$MULTI_ROOT/.lumon.json" <<'EOF'
{
  "plugins": {
    "zillow": {
      "plugin": "browser",
      "search": {
        "url": "https://zillow.com/*",
        "max_results": [1, 50]
      }
    },
    "redfin": {
      "plugin": "browser",
      "search": {
        "url": "https://redfin.com/*",
        "max_results": [1, 20]
      }
    }
  }
}
EOF

# Test: multi-instance browse shows aliases
assert_contains "multi-instance: browse shows zillow" \
    "zillow" \
    "$(cd "$MULTI_ROOT/sandbox" && run browse)"

assert_contains "multi-instance: browse shows redfin" \
    "redfin" \
    "$(cd "$MULTI_ROOT/sandbox" && run browse)"

# Test: browse manifest shows alias namespace
assert_contains "multi-instance: browse manifest shows zillow.search" \
    "zillow.search" \
    "$(cd "$MULTI_ROOT/sandbox" && run browse zillow)"

# Test: instance env var passed to script
assert_eq "multi-instance: instance identity in script" \
    '{"type": "result", "value": "zillow:https://zillow.com/homes"}' \
    "$(run --working-dir "$MULTI_ROOT/sandbox" 'return zillow.search("https://zillow.com/homes")')"

assert_eq "multi-instance: redfin instance identity" \
    '{"type": "result", "value": "redfin:https://redfin.com/homes"}' \
    "$(run --working-dir "$MULTI_ROOT/sandbox" 'return redfin.search("https://redfin.com/homes")')"

# Test: cross-alias contract isolation
assert_contains "multi-instance: zillow rejects redfin URL" \
    '"type": "error"' \
    "$(run --working-dir "$MULTI_ROOT/sandbox" 'return zillow.search("https://redfin.com/123")')"

# ---------------------------------------------------------------------------
# Forced parameter values
# ---------------------------------------------------------------------------

FORCED_ROOT="$TMPDIR_ROOT/forced_project"
mkdir -p "$FORCED_ROOT/sandbox/lumon/manifests" "$FORCED_ROOT/plugins/api"

cat > "$FORCED_ROOT/plugins/api/manifest.lumon" <<'EOF'
define api.call
  "Make an API call"
  takes:
    endpoint: text "API endpoint"
    api_key: text "API key"
  returns: text "Response"
EOF

cat > "$FORCED_ROOT/plugins/api/impl.lumon" <<'EOF'
implement api.call
  let result = plugin.exec("python3 call.py", {endpoint: endpoint, api_key: api_key})
  return result
EOF

cat > "$FORCED_ROOT/plugins/api/call.py" <<'PYEOF'
import json, sys
args = json.load(sys.stdin)
json.dump(f"{args['endpoint']}:{args['api_key']}", sys.stdout)
PYEOF

# Config with forced api_key
cat > "$FORCED_ROOT/.lumon.json" <<'EOF'
{"plugins": {"api": {"call": {"api_key": "sk-secret-123"}}}}
EOF

# Test: forced value injected (agent provides only endpoint)
assert_eq "forced: api_key injected" \
    '{"type": "result", "value": "/users:sk-secret-123"}' \
    "$(run --working-dir "$FORCED_ROOT/sandbox" 'return api.call("/users")')"

# Test: browse hides forced params
BROWSE_FORCED="$(cd "$FORCED_ROOT/sandbox" && run browse api)"
assert_contains "forced: browse shows endpoint" \
    "endpoint" \
    "$BROWSE_FORCED"

# api_key should not appear in browse output (it's forced)
if [[ "$BROWSE_FORCED" == *"api_key"* ]]; then
    fail "forced: browse hides api_key" "(not contain) api_key" "$BROWSE_FORCED"
else
    pass "forced: browse hides api_key"
fi

# ---------------------------------------------------------------------------
# Custom env vars
# ---------------------------------------------------------------------------

ENV_ROOT="$TMPDIR_ROOT/env_project"
mkdir -p "$ENV_ROOT/sandbox/lumon/manifests" "$ENV_ROOT/plugins/svc"

cat > "$ENV_ROOT/plugins/svc/manifest.lumon" <<'EOF'
define svc.ping
  "Ping the service"
  returns: text "Response"
EOF

cat > "$ENV_ROOT/plugins/svc/impl.lumon" <<'EOF'
implement svc.ping
  let result = plugin.exec("python3 ping.py", {})
  return result
EOF

cat > "$ENV_ROOT/plugins/svc/ping.py" <<'PYEOF'
import json, sys, os
api_key = os.environ.get("API_KEY", "none")
base_url = os.environ.get("BASE_URL", "none")
instance = os.environ.get("LUMON_PLUGIN_INSTANCE", "none")
json.dump(f"{instance}:{api_key}:{base_url}", sys.stdout)
PYEOF

cat > "$ENV_ROOT/.lumon.json" <<'EOF'
{
  "plugins": {
    "svc": {
      "env": {
        "API_KEY": "sk-test-456",
        "BASE_URL": "https://api.example.com"
      }
    }
  }
}
EOF

assert_eq "env vars: custom env vars passed to script" \
    '{"type": "result", "value": "svc:sk-test-456:https://api.example.com"}' \
    "$(run --working-dir "$ENV_ROOT/sandbox" 'return svc.ping()')"

# ---------------------------------------------------------------------------
# Namespace conflict (issue #14)
# ---------------------------------------------------------------------------

CONFLICT_ROOT="$TMPDIR_ROOT/conflict_project"
mkdir -p "$CONFLICT_ROOT/sandbox/lumon/manifests" "$CONFLICT_ROOT/plugins/ext"

# Plugin manifest
cat > "$CONFLICT_ROOT/plugins/ext/manifest.lumon" <<'EOF'
define ext.greet
  "Greet someone"
  takes:
    name: text "Name"
  returns: text "Greeting"
EOF

# Plugin impl
cat > "$CONFLICT_ROOT/plugins/ext/impl.lumon" <<'EOF'
implement ext.greet
  let result = plugin.exec("echo hi", {name: name})
  return result
EOF

# .lumon.json enabling the plugin
cat > "$CONFLICT_ROOT/.lumon.json" <<'EOF'
{"plugins": {"ext": {}}}
EOF

# Conflicting disk manifest under the same namespace
cat > "$CONFLICT_ROOT/sandbox/lumon/manifests/ext.lumon" <<'EOF'
define ext.other
  "Other fn"
  returns: text "result"
EOF

assert_contains "namespace conflict: error on collision" \
    "Namespace conflict" \
    "$(run --working-dir "$CONFLICT_ROOT/sandbox" 'return 1')"

# browse specific namespace should also detect conflict
assert_contains "namespace conflict: browse ext detects conflict" \
    "Namespace conflict" \
    "$(cd "$CONFLICT_ROOT/sandbox" && run browse ext 2>&1 || true)"

# browse index should also detect conflict
assert_contains "namespace conflict: browse index detects conflict" \
    "Namespace conflict" \
    "$(cd "$CONFLICT_ROOT/sandbox" && run browse 2>&1 || true)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]]
