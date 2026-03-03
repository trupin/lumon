"""Tests for Lumon bridge system — external plugin extensibility."""

import os
from pathlib import Path

import pytest

from lumon import interpret
from lumon.bridge import parse_bridges
from lumon.errors import LumonError
from lumon.values import LumonTag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_project(
    base: Path,
    bridges_content: str,
    manifests: dict[str, str],
    impls: dict[str, str] | None = None,
) -> str:
    """Create a project layout under *base* with bridges.lumon + manifest files.

    Returns the working directory path as a string.
    """
    lumon_dir = base / "lumon"
    (lumon_dir / "manifests").mkdir(parents=True, exist_ok=True)

    (lumon_dir / "bridges.lumon").write_text(bridges_content)

    for ns, content in manifests.items():
        (lumon_dir / "manifests" / f"{ns}.lumon").write_text(content)

    if impls:
        (lumon_dir / "impl").mkdir(exist_ok=True)
        for ns, content in impls.items():
            (lumon_dir / "impl" / f"{ns}.lumon").write_text(content)

    return str(base)


def mock_executor(name, args, run_cmd, working_dir):
    """Default mock executor — returns args as a map."""
    return args


# ---------------------------------------------------------------------------
# parse_bridges
# ---------------------------------------------------------------------------

class TestParseBridges:
    def test_single_bridge(self):
        source = 'bridge browser.search\n  run: "python3 plugins/search.py"'
        result = parse_bridges(source)
        assert result == {"browser.search": "python3 plugins/search.py"}

    def test_multiple_bridges(self):
        source = (
            'bridge browser.search\n  run: "python3 plugins/search.py"\n\n'
            'bridge db.query\n  run: "./plugins/db_query"'
        )
        result = parse_bridges(source)
        assert result == {
            "browser.search": "python3 plugins/search.py",
            "db.query": "./plugins/db_query",
        }

    def test_comments_and_blank_lines(self):
        source = (
            "-- A comment\n\n"
            'bridge foo.bar\n  run: "cmd"\n\n'
            "-- Another comment\n"
        )
        result = parse_bridges(source)
        assert result == {"foo.bar": "cmd"}

    def test_incomplete_bridge(self):
        source = "bridge foo.bar\n"
        with pytest.raises(Exception, match="Incomplete bridge"):
            parse_bridges(source)

    def test_missing_run_directive(self):
        source = "bridge foo.bar\n  something: else"
        with pytest.raises(Exception, match="expected 'run:'"):
            parse_bridges(source)

    def test_empty_source(self):
        assert parse_bridges("") == {}

    def test_duplicate_bridge_name(self):
        """Second declaration with same name overwrites the first."""
        source = (
            'bridge foo.bar\n  run: "cmd1"\n\n'
            'bridge foo.bar\n  run: "cmd2"'
        )
        result = parse_bridges(source)
        assert result == {"foo.bar": "cmd2"}


# ---------------------------------------------------------------------------
# Bridge calls via interpret()
# ---------------------------------------------------------------------------

SEARCH_MANIFEST = '''\
define browser.search
  "Search the web"
  takes:
    query: text "Search query"
    max_results: number "Max results" = 10
  returns: text "Results"
'''

BRIDGES_CONF = '''\
bridge browser.search
  run: "python3 plugins/search.py"
'''


class TestBridgeCall:
    def test_basic_call(self, tmp_path):
        """Bridge call returns the executor's result."""
        results = []

        def executor(name, args, run_cmd, working_dir):
            results.append((name, args, run_cmd))
            return "search results"

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("austin tx")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "search results"
        assert results[0][0] == "browser.search"
        assert results[0][1]["query"] == "austin tx"
        assert results[0][2] == "python3 plugins/search.py"

    def test_named_args(self, tmp_path):
        """Args dict uses param names from define, not positional indices."""
        captured = {}

        def executor(name, args, run_cmd, working_dir):
            captured.update(args)
            return "ok"

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("test query", 5)'
        interpret(code, working_dir=wd, bridge_executor=executor)
        assert captured["query"] == "test query"
        assert captured["max_results"] == 5

    def test_default_args(self, tmp_path):
        """Missing args use defaults from define."""
        captured = {}

        def executor(name, args, run_cmd, working_dir):
            captured.update(args)
            return "ok"

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("test query")'
        interpret(code, working_dir=wd, bridge_executor=executor)
        assert captured["query"] == "test query"
        assert captured["max_results"] == 10

    def test_tag_return(self, tmp_path):
        """Executor can return LumonTag values."""
        def executor(name, args, run_cmd, working_dir):
            return LumonTag("ok", ["result1", "result2"])

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("test")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == {"tag": "ok", "value": ["result1", "result2"]}

    def test_error_return(self, tmp_path):
        """Executor returning an error tag propagates correctly."""
        def executor(name, args, run_cmd, working_dir):
            return LumonTag("error", "connection failed")

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("test")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == {"tag": "error", "value": "connection failed"}

    def test_implement_takes_precedence(self, tmp_path):
        """implement + bridge both exist -> implement wins, executor never called."""
        executor_called = []

        def executor(name, args, run_cmd, working_dir):
            executor_called.append(True)
            return "from bridge"

        impl = '''\
implement browser.search
  return "from implement"
'''
        wd = make_project(
            tmp_path,
            BRIDGES_CONF,
            {"browser": SEARCH_MANIFEST},
            impls={"browser": impl},
        )
        code = 'return browser.search("test")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "from implement"
        assert executor_called == []

    def test_no_define_error(self, tmp_path):
        """Bridge without matching define -> interpreter error at load time."""
        bridges = 'bridge missing.func\n  run: "cmd"'
        wd = make_project(tmp_path, bridges, {})
        r = interpret("return 1", working_dir=wd, bridge_executor=mock_executor)
        assert r["type"] == "error"
        assert "no matching define" in r["message"]

    def test_pipe_support(self, tmp_path):
        """value |> bridged.fn works."""
        def executor(name, args, run_cmd, working_dir):
            return f"piped: {args['query']}"

        manifest = '''\
define browser.search
  "Search"
  takes:
    query: text "Query"
  returns: text "Results"
'''
        bridges = 'bridge browser.search\n  run: "cmd"'
        wd = make_project(tmp_path, bridges, {"browser": manifest})
        code = 'return "hello" |> browser.search'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "piped: hello"

    def test_no_bridges_file(self, tmp_path):
        """Missing bridges.lumon -> no error, no bridges."""
        (tmp_path / "lumon").mkdir()
        code = "return 42"
        r = interpret(code, working_dir=str(tmp_path))
        assert r["type"] == "result"
        assert r["value"] == 42

    def test_multiple_bridges(self, tmp_path):
        """Two bridges in one file both work."""
        call_log = []

        def executor(name, args, run_cmd, working_dir):
            call_log.append(name)
            return f"result from {name}"

        manifests = {
            "browser": '''\
define browser.search
  "Search"
  takes:
    query: text "Query"
  returns: text "Results"
''',
            "db": '''\
define db.query
  "Query DB"
  takes:
    sql: text "SQL"
  returns: text "Results"
''',
        }
        bridges = (
            'bridge browser.search\n  run: "cmd1"\n\n'
            'bridge db.query\n  run: "cmd2"'
        )
        wd = make_project(tmp_path, bridges, manifests)
        code = '''\
let a = browser.search("test")
let b = db.query("SELECT 1")
return a'''
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert "browser.search" in call_log
        assert "db.query" in call_log

    def test_too_many_args(self, tmp_path):
        """Extra positional args beyond the define params are silently ignored."""
        captured = {}

        def executor(name, args, run_cmd, working_dir):
            captured.update(args)
            return "ok"

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("query", 5, "extra")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        # Only the defined params are in args — extra positional is ignored
        assert set(captured.keys()) == {"query", "max_results"}

    def test_zero_param_define(self, tmp_path):
        """Bridge with no takes: clause sends empty args dict."""
        captured = {}

        def executor(name, args, run_cmd, working_dir):
            captured["args"] = args
            return "pong"

        manifest = '''\
define ext.ping
  "Ping the service"
  returns: text "Pong"
'''
        bridges = 'bridge ext.ping\n  run: "cmd"'
        wd = make_project(tmp_path, bridges, {"ext": manifest})
        code = "return ext.ping()"
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "pong"
        assert captured["args"] == {}

    def test_executor_raising_error(self, tmp_path):
        """LumonError from executor surfaces as {"type": "error"} envelope."""
        def executor(name, args, run_cmd, working_dir):
            raise LumonError(f"Bridge '{name}' executable not found: {run_cmd}")

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = 'return browser.search("test")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "error"
        assert "executable not found" in r["message"]

    def test_match_on_bridge_result(self, tmp_path):
        """Call bridge, match on :ok/:error tag, verify destructured payload."""
        def executor(name, args, run_cmd, working_dir):
            return LumonTag("ok", ["123 Main St", "456 Oak Ave"])

        wd = make_project(tmp_path, BRIDGES_CONF, {"browser": SEARCH_MANIFEST})
        code = '''\
let result = browser.search("austin")
match result
  :ok(items) -> return items
  :error(msg) -> return msg'''
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == ["123 Main St", "456 Oak Ave"]

    def test_bridge_called_from_implement(self, tmp_path):
        """Implement block calls a bridged function internally."""
        def executor(name, args, run_cmd, working_dir):
            return LumonTag("ok", "bridge result")

        browser_manifest = '''\
define browser.search
  "Search"
  takes:
    query: text "Query"
  returns: text "Results"
'''
        search_manifest = '''\
define search.homes
  "Search homes wrapper"
  takes:
    query: text "Query"
  returns: text "Results"
'''
        impl = '''\
implement search.homes
  let results = browser.search(query)
  match results
    :ok(data) -> return data
    :error(msg) -> return :error("search failed: " + msg)
'''
        bridges = 'bridge browser.search\n  run: "cmd"'
        wd = make_project(
            tmp_path, bridges,
            {"browser": browser_manifest, "search": search_manifest},
            impls={"search": impl},
        )
        code = 'return search.homes("austin")'
        r = interpret(code, working_dir=wd, bridge_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "bridge result"
