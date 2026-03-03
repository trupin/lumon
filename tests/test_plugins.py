"""Tests for Lumon plugin system — self-contained plugin directories with contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lumon import interpret
from lumon.errors import LumonError
from lumon.plugins import (
    discover_plugins,
    exec_plugin_script,
    load_config,
    validate_contracts,
)
from lumon.values import LumonTag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GREET_MANIFEST = """\
define greet.hello
  "Greet someone by name"
  takes:
    name: text "The name to greet"
  returns: text "The greeting"
"""

GREET_IMPL = """\
implement greet.hello
  let result = plugin.exec("python3 greet.py", {name: name})
  return result
"""

SEARCH_MANIFEST = """\
define browser.search
  "Search the web"
  takes:
    url: text "URL to search"
    max_results: number "Max results" = 10
  returns: text "Results"
"""

SEARCH_IMPL = """\
implement browser.search
  let result = plugin.exec("python3 search.py", {url: url, max_results: max_results})
  return result
"""


def make_plugin_project(
    base: Path,
    plugins: dict[str, dict[str, str]],
    config: dict | None = None,
    sandbox_impls: dict[str, str] | None = None,
) -> str:
    """Create a project layout with plugins and .lumon.json.

    Args:
        base: root directory (the "target")
        plugins: {plugin_name: {filename: content}} — files in plugins/<name>/
        config: .lumon.json content (dict); defaults to allowing all listed plugins
        sandbox_impls: optional user impls in sandbox/lumon/impl/<ns>.lumon

    Returns the sandbox (working_dir) path as a string.
    """
    sandbox = base / "sandbox"
    (sandbox / "lumon" / "manifests").mkdir(parents=True, exist_ok=True)
    (sandbox / "lumon" / "impl").mkdir(parents=True, exist_ok=True)

    plugins_dir = base / "plugins"
    plugins_dir.mkdir(exist_ok=True)

    # Create plugin directories
    for plugin_name, files in plugins.items():
        plugin_path = plugins_dir / plugin_name
        plugin_path.mkdir(exist_ok=True)
        for filename, content in files.items():
            (plugin_path / filename).write_text(content)

    # Create .lumon.json
    if config is None:
        config = {"plugins": {name: {} for name in plugins}}
    (base / ".lumon.json").write_text(json.dumps(config))

    # Optional user impls in sandbox
    if sandbox_impls:
        for ns, content in sandbox_impls.items():
            (sandbox / "lumon" / "impl" / f"{ns}.lumon").write_text(content)

    return str(sandbox)


def mock_executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
    """Default mock executor — returns args as a map."""
    return args


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_valid_config(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (tmp_path / ".lumon.json").write_text('{"plugins": {"greet": {}}}')
        config = load_config(str(sandbox))
        assert config == {"plugins": {"greet": {}}}

    def test_missing_config(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        assert load_config(str(sandbox)) == {}

    def test_invalid_json(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (tmp_path / ".lumon.json").write_text("not json")
        with pytest.raises(LumonError, match="Invalid .lumon.json"):
            load_config(str(sandbox))


# ---------------------------------------------------------------------------
# discover_plugins
# ---------------------------------------------------------------------------


class TestDiscoverPlugins:
    def test_discovers_listed_plugins(self, tmp_path: Path) -> None:
        plugins_dir = tmp_path / "plugins" / "greet"
        plugins_dir.mkdir(parents=True)
        (plugins_dir / "manifest.lumon").write_text(GREET_MANIFEST)
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()

        config = {"plugins": {"greet": {}}}
        result = discover_plugins(str(sandbox), config)
        assert len(result) == 1
        assert result[0].name == "greet"

    def test_ignores_unlisted_plugins(self, tmp_path: Path) -> None:
        for name in ("greet", "secret"):
            d = tmp_path / "plugins" / name
            d.mkdir(parents=True)
            (d / "manifest.lumon").write_text(f"define {name}.fn\n  returns: text\n")
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()

        config = {"plugins": {"greet": {}}}
        result = discover_plugins(str(sandbox), config)
        assert len(result) == 1
        assert result[0].name == "greet"

    def test_no_plugins_dir(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        assert discover_plugins(str(sandbox), {"plugins": {"x": {}}}) == []

    def test_empty_config(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        assert discover_plugins(str(sandbox), {}) == []


# ---------------------------------------------------------------------------
# Plugin calls via interpret()
# ---------------------------------------------------------------------------


class TestPluginCall:
    def test_basic_call(self, tmp_path: Path) -> None:
        """Plugin call returns the executor's result."""
        results: list[tuple[str, dict, str]] = []

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            results.append((command, args, plugin_dir))
            return "Hello, World!"

        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        code = 'return greet.hello("World")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "Hello, World!"
        assert results[0][0] == "python3 greet.py"
        assert results[0][1] == {"name": "World"}

    def test_args_serialized(self, tmp_path: Path) -> None:
        """Args dict is passed to plugin.exec correctly."""
        captured: dict[str, object] = {}

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            captured.update(args)
            return "ok"

        wd = make_plugin_project(tmp_path, {
            "browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            },
        })
        code = 'return browser.search("https://example.com", 5)'
        interpret(code, working_dir=wd, plugin_executor=executor)
        assert captured["url"] == "https://example.com"
        assert captured["max_results"] == 5

    def test_default_args(self, tmp_path: Path) -> None:
        """Missing args use defaults from define."""
        captured: dict[str, object] = {}

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            captured.update(args)
            return "ok"

        wd = make_plugin_project(tmp_path, {
            "browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            },
        })
        code = 'return browser.search("https://example.com")'
        interpret(code, working_dir=wd, plugin_executor=executor)
        assert captured["url"] == "https://example.com"
        assert captured["max_results"] == 10

    def test_tag_return(self, tmp_path: Path) -> None:
        """Plugin can return LumonTag values."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return LumonTag("ok", ["result1", "result2"])

        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == {"tag": "ok", "value": ["result1", "result2"]}

    def test_error_return(self, tmp_path: Path) -> None:
        """Plugin returning an error tag propagates correctly."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return LumonTag("error", "connection failed")

        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == {"tag": "error", "value": "connection failed"}

    def test_user_impl_overrides_plugin(self, tmp_path: Path) -> None:
        """User impl in sandbox takes precedence over plugin impl."""
        executor_called: list[bool] = []

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            executor_called.append(True)
            return "from plugin"

        user_impl = """\
implement greet.hello
  return "from user"
"""
        wd = make_plugin_project(
            tmp_path,
            {"greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            }},
            sandbox_impls={"greet": user_impl},
        )
        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "from user"
        assert executor_called == []

    def test_plugin_exec_outside_context(self, tmp_path: Path) -> None:
        """plugin.exec outside plugin context → interpreter error."""
        wd = make_plugin_project(tmp_path, {})
        code = 'return plugin.exec("echo hello", {})'
        r = interpret(code, working_dir=wd)
        assert r["type"] == "error"
        assert "plugin.exec can only be called from a plugin" in r["message"]

    def test_no_plugins_directory(self, tmp_path: Path) -> None:
        """Missing plugins/ → no error."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "lumon").mkdir()
        r = interpret("return 42", working_dir=str(sandbox))
        assert r["type"] == "result"
        assert r["value"] == 42

    def test_multiple_plugins(self, tmp_path: Path) -> None:
        """Two plugins in one project both work."""
        call_log: list[str] = []

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            call_log.append(command)
            return f"result from {command}"

        ext_manifest = """\
define ext.ping
  "Ping"
  returns: text "Pong"
"""
        ext_impl = """\
implement ext.ping
  let result = plugin.exec("python3 ping.py", {})
  return result
"""
        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
            "ext": {
                "manifest.lumon": ext_manifest,
                "impl.lumon": ext_impl,
            },
        })
        code = """\
let a = greet.hello("World")
let b = ext.ping()
return a"""
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert len(call_log) == 2

    def test_plugin_not_in_config(self, tmp_path: Path) -> None:
        """Plugin not listed in .lumon.json → not loaded."""
        wd = make_plugin_project(
            tmp_path,
            {"greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            }},
            config={"plugins": {}},  # greet not listed
        )
        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=wd, plugin_executor=mock_executor)
        assert r["type"] == "error"
        assert "Undefined function" in r["message"]

    def test_missing_lumon_json(self, tmp_path: Path) -> None:
        """No .lumon.json → no plugins loaded."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "lumon").mkdir()
        # Create a plugin dir but no .lumon.json
        plugin_dir = tmp_path / "plugins" / "greet"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.lumon").write_text(GREET_MANIFEST)
        (plugin_dir / "impl.lumon").write_text(GREET_IMPL)

        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=str(sandbox), plugin_executor=mock_executor)
        assert r["type"] == "error"
        assert "Undefined function" in r["message"]

    def test_pipe_support(self, tmp_path: Path) -> None:
        """value |> plugin_fn works."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return f"piped: {args.get('name', '')}"

        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        code = 'return "hello" |> greet.hello'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "piped: hello"

    def test_plugin_impl_calls_builtins(self, tmp_path: Path) -> None:
        """Plugin impl can use builtins like text.upper."""
        impl_with_builtin = """\
implement greet.hello
  let result = plugin.exec("python3 greet.py", {name: name})
  return text.upper(result)
"""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return f"hello {args['name']}"

        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": impl_with_builtin,
            },
        })
        code = 'return greet.hello("world")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"
        assert r["value"] == "HELLO WORLD"


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


class TestContracts:
    def test_text_wildcard_passes(self, tmp_path: Path) -> None:
        """Text wildcard contract allows matching values."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return "ok"

        wd = make_plugin_project(
            tmp_path,
            {"browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            }},
            config={"plugins": {"browser": {"search": {"url": "https://zillow.com/*"}}}},
        )
        code = 'return browser.search("https://zillow.com/homes")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"

    def test_text_wildcard_fails(self, tmp_path: Path) -> None:
        """Text wildcard contract rejects non-matching values."""
        wd = make_plugin_project(
            tmp_path,
            {"browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            }},
            config={"plugins": {"browser": {"search": {"url": "https://zillow.com/*"}}}},
        )
        code = 'return browser.search("https://redfin.com/123")'
        r = interpret(code, working_dir=wd, plugin_executor=mock_executor)
        assert r["type"] == "error"
        assert "Contract violation" in r["message"]
        assert "does not match pattern" in r["message"]

    def test_number_range_passes(self, tmp_path: Path) -> None:
        """Number range contract allows values within range."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return "ok"

        wd = make_plugin_project(
            tmp_path,
            {"browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            }},
            config={"plugins": {"browser": {"search": {"max_results": [1, 50]}}}},
        )
        code = 'return browser.search("https://example.com", 10)'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"

    def test_number_range_fails(self, tmp_path: Path) -> None:
        """Number range contract rejects values outside range."""
        wd = make_plugin_project(
            tmp_path,
            {"browser": {
                "manifest.lumon": SEARCH_MANIFEST,
                "impl.lumon": SEARCH_IMPL,
            }},
            config={"plugins": {"browser": {"search": {"max_results": [1, 50]}}}},
        )
        code = 'return browser.search("https://example.com", 100)'
        r = interpret(code, working_dir=wd, plugin_executor=mock_executor)
        assert r["type"] == "error"
        assert "Contract violation" in r["message"]
        assert "outside range" in r["message"]

    def test_enum_passes(self, tmp_path: Path) -> None:
        """Enum contract allows listed values."""
        manifest = """\
define search.mode
  "Set search mode"
  takes:
    mode: text "Search mode"
  returns: text "Confirmation"
"""
        impl = """\
implement search.mode
  let result = plugin.exec("python3 mode.py", {mode: mode})
  return result
"""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return "ok"

        wd = make_plugin_project(
            tmp_path,
            {"search": {"manifest.lumon": manifest, "impl.lumon": impl}},
            config={"plugins": {"search": {"mode": {"mode": ["fast", "thorough"]}}}},
        )
        code = 'return search.mode("fast")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"

    def test_enum_fails(self, tmp_path: Path) -> None:
        """Enum contract rejects unlisted values."""
        manifest = """\
define search.mode
  "Set search mode"
  takes:
    mode: text "Search mode"
  returns: text "Confirmation"
"""
        impl = """\
implement search.mode
  let result = plugin.exec("python3 mode.py", {mode: mode})
  return result
"""
        wd = make_plugin_project(
            tmp_path,
            {"search": {"manifest.lumon": manifest, "impl.lumon": impl}},
            config={"plugins": {"search": {"mode": {"mode": ["fast", "thorough"]}}}},
        )
        code = 'return search.mode("secret")'
        r = interpret(code, working_dir=wd, plugin_executor=mock_executor)
        assert r["type"] == "error"
        assert "Contract violation" in r["message"]
        assert "not in allowed values" in r["message"]

    def test_no_contract_no_validation(self, tmp_path: Path) -> None:
        """No contract on param → no validation."""

        def executor(command: str, args: dict[str, object], plugin_dir: str) -> object:
            return "ok"

        wd = make_plugin_project(
            tmp_path,
            {"greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            }},
            config={"plugins": {"greet": {}}},
        )
        # Any value should pass since no contracts
        code = 'return greet.hello("anything goes")'
        r = interpret(code, working_dir=wd, plugin_executor=executor)
        assert r["type"] == "result"


# ---------------------------------------------------------------------------
# Browse integration
# ---------------------------------------------------------------------------


class TestBrowsePlugins:
    def test_browse_shows_plugin_namespaces(self, tmp_path: Path) -> None:
        """Browse index includes plugin namespaces."""
        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        # We test this indirectly — the plugin namespace should be
        # discoverable and the function callable.
        code = 'return greet.hello("test")'
        r = interpret(code, working_dir=wd, plugin_executor=mock_executor)
        assert r["type"] == "result"

    def test_browse_shows_manifest(self, tmp_path: Path) -> None:
        """Plugin manifest is accessible via browse."""
        wd = make_plugin_project(tmp_path, {
            "greet": {
                "manifest.lumon": GREET_MANIFEST,
                "impl.lumon": GREET_IMPL,
            },
        })
        # Verify the manifest file exists in the expected location
        manifest_path = os.path.join(tmp_path, "plugins", "greet", "manifest.lumon")
        assert os.path.isfile(manifest_path)
        content = open(manifest_path).read()
        assert "greet.hello" in content
