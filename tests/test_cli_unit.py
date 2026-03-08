"""Unit tests for lumon.cli — testing CLI functions directly in pytest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lumon.cli import (
    _annotate_manifest,
    _batch_size_from_result,
    _bundled_manifest,
    _clear_state,
    _deploy_plugin_skills,
    _deploy_skills,
    _format_contract,
    _load_state,
    _prompt_overwrite,
    _STATE_FILE,
    _save_state,
    cmd_browse,
    cmd_deploy,
    cmd_respond,
    cmd_run_code,
    cmd_spec,
    cmd_test,
    cmd_version,
    main,
)


class TestStateHelpers:
    def test_save_and_load_state(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [])
            state = _load_state()
            assert state is not None
            assert state["code"] == "return 42"
            assert state["responses"] == []
            assert state["batch_size"] == 0

    def test_save_and_load_state_with_batch_size(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [], batch_size=3)
            state = _load_state()
            assert state is not None
            assert state["batch_size"] == 3

    def test_load_state_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            assert _load_state() is None

    def test_clear_state(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [])
            _clear_state()
            assert _load_state() is None

    def test_clear_state_noop_if_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _clear_state()  # should not raise


class TestCmdVersion:
    def test_prints_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = cmd_version()
        assert result == 0
        captured = capsys.readouterr()
        assert "lumon" in captured.out


class TestCmdSpec:
    def test_prints_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace()
        result = cmd_spec(args)
        assert result == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 100


class TestCmdRunCode:
    def test_simple_return(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                result = cmd_run_code("return 42")
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == 42

    def test_error_returns_1(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                result = cmd_run_code("return undefined_var")
            finally:
                os.chdir(old_cwd)
        assert result == 1

    def test_ask_saves_state(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                cmd_run_code('let x = ask\n  "what?"')
            finally:
                os.chdir(old_cwd)
        assert state_file.exists()


class TestCmdRespond:
    def test_no_state_error(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            args = argparse.Namespace(response='"hello"')
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "no suspended execution" in captured.err

    def test_invalid_json(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [])
            args = argparse.Namespace(response="not json{")
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "invalid JSON" in captured.err

    def test_respond_resumes(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state('let x = ask\n  "what?"\nreturn x', [])
                args = argparse.Namespace(response='"the answer"')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "the answer"


    def test_respond_with_builtins(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """respond should have io/text/list builtins available during replay."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                code = 'let n = text.length("hello")\nlet x = ask\n  "how?"\n  context: {n: n}\nreturn x'
                _save_state(code, [])
                args = argparse.Namespace(response='"ok"')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "ok"


class TestBatchSizeFromResult:
    def test_non_spawn_returns_zero(self) -> None:
        assert _batch_size_from_result({"type": "result", "value": 42}) == 0
        assert _batch_size_from_result({"type": "ask", "prompt": "?"}) == 0

    def test_single_spawn(self) -> None:
        assert _batch_size_from_result({"type": "spawn_batch", "prompt": "do X"}) == 1

    def test_multiple_spawns(self) -> None:
        result = {"type": "spawn_batch", "spawns": [{"prompt": "A"}, {"prompt": "B"}, {"prompt": "C"}]}
        assert _batch_size_from_result(result) == 3


class TestRespondBatch:
    def test_respond_batch_array(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Responding with a JSON array matching batch_size feeds all responses at once."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let a = spawn\n  "Task A"\nlet b = spawn\n  "Task B"\nreturn [a, b]'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                # Save state as if we just ran the code and got a spawn_batch with 2 spawns
                _save_state(code, [], batch_size=2)
                args = argparse.Namespace(response='["resp A", "resp B"]')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == ["resp A", "resp B"]

    def test_respond_single_still_works(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Responding with a single JSON value (not array) works even when batch_size > 1."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let x = ask\n  "what?"\nreturn x'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state(code, [], batch_size=0)
                args = argparse.Namespace(response='"hello"')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "hello"

    def test_respond_array_wrong_size_treated_as_single(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Array with length != batch_size is treated as a single response."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let x = ask\n  "what?"\nreturn x'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state(code, [], batch_size=3)
                args = argparse.Namespace(response='["a", "b"]')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        # The list is treated as a single value
        assert output["value"] == ["a", "b"]

    def test_respond_batch_dict(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Responding with a dict keyed by spawn_N distributes responses."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let a = spawn\n  "Task A"\nlet b = spawn\n  "Task B"\nreturn [a, b]'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state(code, [], batch_size=2)
                args = argparse.Namespace(response='{"spawn_0": "hello", "spawn_1": "world"}')
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == ["hello", "world"]

    def test_respond_from_file(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """respond --file reads JSON from a file."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        response_file = Path(str(tmp_path)) / "response.json"
        response_file.write_text('"hello from file"', encoding="utf-8")
        code = 'let x = ask\n  "what?"\nreturn x'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state(code, [])
                args = argparse.Namespace(response=None, file=str(response_file))
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "hello from file"
        assert output["cleanup"] == [str(response_file)]

    def test_respond_file_not_found(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """respond --file with missing file returns error."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [])
            args = argparse.Namespace(response=None, file="/nonexistent/file.json")
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "file not found" in captured.err

    def test_respond_from_stdin(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """respond with '-' reads JSON from stdin."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let x = ask\n  "what?"\nreturn x'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                _save_state(code, [])
                args = argparse.Namespace(response="-", file=None)
                with patch("sys.stdin") as mock_stdin:
                    mock_stdin.read.return_value = '"from stdin"'
                    result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "from stdin"

    def test_respond_no_args_error(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """respond with no response and no --file returns error."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state("return 42", [])
            args = argparse.Namespace(response=None, file=None)
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "provide a JSON response" in captured.err

    def test_run_code_saves_batch_size(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """cmd_run_code saves batch_size in state when spawn_batch is returned."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let a = spawn\n  "Task A"\nlet b = spawn\n  "Task B"\nreturn [a, b]'
        with patch("lumon.cli._STATE_FILE", state_file):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                cmd_run_code(code)
            finally:
                os.chdir(old_cwd)
            state = _load_state()
        assert state is not None
        assert state["batch_size"] == 2


class TestCmdBrowse:
    def test_browse_builtin_namespace(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            args = argparse.Namespace(namespace="io")
            result = cmd_browse(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "io" in captured.out

    def test_browse_missing_namespace(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            args = argparse.Namespace(namespace="nonexistent")
            result = cmd_browse(args)
        finally:
            os.chdir(old_cwd)
        assert result == 1

    def test_browse_index(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            args = argparse.Namespace(namespace=None)
            result = cmd_browse(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "io" in captured.out

    def test_browse_disk_manifest(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        manifest_dir = os.path.join(root, "lumon", "manifests")
        os.makedirs(manifest_dir)
        with open(os.path.join(manifest_dir, "inbox.lumon"), "w", encoding="utf-8") as f:
            f.write('define inbox.read\n  "Read"\n  returns: list<text>\n')
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            args = argparse.Namespace(namespace="inbox")
            result = cmd_browse(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "inbox.read" in captured.out


class TestCmdTest:
    def test_no_tests_dir(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            args = argparse.Namespace(namespace=None)
            result = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "No tests found" in captured.out

    def test_run_passing_test(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        test_dir = os.path.join(root, "lumon", "tests")
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, "simple.lumon"), "w", encoding="utf-8") as f:
            f.write("return 42\n")
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            args = argparse.Namespace(namespace=None)
            result = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out

    def test_run_failing_test(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        test_dir = os.path.join(root, "lumon", "tests")
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, "fail.lumon"), "w", encoding="utf-8") as f:
            f.write("return undefined_var\n")
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            args = argparse.Namespace(namespace=None)
            result = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        assert result == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.out

    def test_missing_test_file(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        test_dir = os.path.join(root, "lumon", "tests")
        os.makedirs(test_dir)
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            args = argparse.Namespace(namespace="nonexistent")
            result = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "SKIP" in captured.out


    def test_test_loads_user_functions(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Test runner loads user-defined functions from manifests/ and impl/."""
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        # Create manifest
        manifest_dir = os.path.join(root, "lumon", "manifests")
        os.makedirs(manifest_dir)
        with open(os.path.join(manifest_dir, "myns.lumon"), "w", encoding="utf-8") as f:
            f.write('define myns.double\n  "Double a number"\n  takes:\n    n: number "The number"\n  returns: number "The result"\n')
        # Create impl
        impl_dir = os.path.join(root, "lumon", "impl")
        os.makedirs(impl_dir)
        with open(os.path.join(impl_dir, "myns.lumon"), "w", encoding="utf-8") as f:
            f.write("implement myns.double\n  return n * 2\n")
        # Create test that calls the user function
        test_dir = os.path.join(root, "lumon", "tests")
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, "myns.lumon"), "w", encoding="utf-8") as f:
            f.write("test myns.double\n  assert myns.double(3) == 6\n")
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            args = argparse.Namespace(namespace="myns")
            result = cmd_test(args)
        finally:
            os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        assert "PASS  myns.double" in captured.out


class TestCmdDeploy:
    def test_deploy_to_target(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        result = cmd_deploy(args)
        assert result == 0
        assert os.path.isfile(os.path.join(target, "CLAUDE.md"))
        assert os.path.isdir(os.path.join(target, ".claude"))
        assert os.path.isdir(os.path.join(target, "sandbox"))
        assert os.path.isdir(os.path.join(target, "plugins"))
        assert os.path.isfile(os.path.join(target, ".lumon.json"))
        # Skills deployed
        skills_dir = os.path.join(target, ".claude", "skills")
        assert os.path.isdir(skills_dir)
        for skill in ("ask-spawn", "code-organization", "issues", "lumon", "plugins-issues", "review", "workflow"):
            assert os.path.isfile(os.path.join(skills_dir, skill, "SKILL.md"))
        # Plugin skills deployed
        plugin_skills_dir = os.path.join(target, "plugins", ".claude", "skills")
        assert os.path.isdir(plugin_skills_dir)
        for skill in ("fix-issues",):
            assert os.path.isfile(os.path.join(plugin_skills_dir, skill, "SKILL.md"))

    def test_deploy_identical_is_noop(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        # First deploy
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Second deploy — identical files silently skipped
        result = cmd_deploy(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Nothing to deploy" in captured.out

    def test_deploy_modified_file_prompts(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify CLAUDE.md
        claude_md = os.path.join(target, "CLAUDE.md")
        with open(claude_md, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Redeploy — answer No
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = cmd_deploy(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Skipped" in captured.out
        assert "CLAUDE.md" in captured.out

    def test_deploy_force_overwrites_modified(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify CLAUDE.md
        claude_md = os.path.join(target, "CLAUDE.md")
        with open(claude_md, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Force deploy — overwrites without prompt
        args = argparse.Namespace(target=target, force=True)
        result = cmd_deploy(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Deployed" in captured.out
        with open(claude_md, encoding="utf-8") as f:
            assert "# user edit" not in f.read()

    def test_deploy_skills_identical_skipped_silently(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Second deploy — identical skills should not appear in output at all
        cmd_deploy(args)
        captured = capsys.readouterr()
        assert "ask-spawn" not in captured.out

    def test_deploy_skills_conflict_prompt_no(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify a skill
        skill_path = os.path.join(target, ".claude", "skills", "workflow", "SKILL.md")
        with open(skill_path, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Redeploy — answer No
        monkeypatch.setattr("builtins.input", lambda _: "n")
        cmd_deploy(args)
        captured = capsys.readouterr()
        assert "workflow" in captured.out
        assert "Skipped" in captured.out
        # Verify the user edit is preserved
        with open(skill_path, encoding="utf-8") as f:
            assert "# user edit" in f.read()

    def test_deploy_skills_conflict_prompt_yes(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify a skill
        skill_path = os.path.join(target, ".claude", "skills", "ask-spawn", "SKILL.md")
        with open(skill_path, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Redeploy — answer Yes
        monkeypatch.setattr("builtins.input", lambda _: "y")
        cmd_deploy(args)
        captured = capsys.readouterr()
        assert "ask-spawn" in captured.out
        assert "Deployed" in captured.out
        # Verify the user edit is gone (overwritten)
        with open(skill_path, encoding="utf-8") as f:
            assert "# user edit" not in f.read()

    def test_deploy_skills_force_skips_prompt(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify a skill
        skill_path = os.path.join(target, ".claude", "skills", "workflow", "SKILL.md")
        with open(skill_path, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Force deploy — no prompt, overwrites
        args = argparse.Namespace(target=target, force=True)
        cmd_deploy(args)
        captured = capsys.readouterr()
        assert "Deployed" in captured.out
        with open(skill_path, encoding="utf-8") as f:
            assert "# user edit" not in f.read()

    def test_deploy_prompt_eof_skips(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "project")
        os.makedirs(target)
        args = argparse.Namespace(target=target, force=False)
        cmd_deploy(args)
        capsys.readouterr()
        # Modify CLAUDE.md
        claude_md = os.path.join(target, "CLAUDE.md")
        with open(claude_md, "a", encoding="utf-8") as f:
            f.write("\n# user edit\n")
        # Simulate EOFError (non-interactive stdin)
        def raise_eof(_: str) -> str:
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        result = cmd_deploy(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Skipped" in captured.out
        # User edit preserved
        with open(claude_md, encoding="utf-8") as f:
            assert "# user edit" in f.read()

    def test_deploy_missing_target(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "nonexistent")
        args = argparse.Namespace(target=target, force=False)
        result = cmd_deploy(args)
        assert result == 1


class TestDeploySkills:
    def test_deploy_skills_returns_expected_skills(self) -> None:
        skills = _deploy_skills()
        assert isinstance(skills, dict)
        assert sorted(skills.keys()) == ["ask-spawn", "auto-deploy", "code-organization", "issues", "lumon", "plugins-issues", "review", "workflow"]
        for name, content in skills.items():
            assert len(content) > 0, f"Skill '{name}' has empty content"
            assert "---" in content, f"Skill '{name}' missing frontmatter"

    def test_deploy_plugin_skills_returns_expected_skills(self) -> None:
        skills = _deploy_plugin_skills()
        assert isinstance(skills, dict)
        assert sorted(skills.keys()) == ["fix-issues"]
        for name, content in skills.items():
            assert len(content) > 0, f"Plugin skill '{name}' has empty content"
            assert "---" in content, f"Plugin skill '{name}' missing frontmatter"

    def test_prompt_overwrite_eof_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_eof(_: str) -> str:
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        assert _prompt_overwrite("test.md") is False

    def test_prompt_overwrite_keyboard_interrupt_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_ki(_: str) -> str:
            raise KeyboardInterrupt
        monkeypatch.setattr("builtins.input", raise_ki)
        assert _prompt_overwrite("test.md") is False


class TestBundledManifest:
    def test_existing_manifest(self) -> None:
        result = _bundled_manifest("io.lumon")
        assert result is not None
        assert "io" in result

    def test_missing_manifest(self) -> None:
        result = _bundled_manifest("nonexistent.lumon")
        assert result is None


class TestFormatContract:
    def test_string_contract(self) -> None:
        assert _format_contract("https://example.com/*") == "https://example.com/*"

    def test_number_range(self) -> None:
        assert _format_contract([1, 100]) == "1-100"

    def test_string_enum(self) -> None:
        assert _format_contract(["a", "b", "c"]) == "a | b | c"

    def test_other_type(self) -> None:
        result = _format_contract({"key": "value"})
        assert isinstance(result, str)


class TestAnnotateManifest:
    def test_no_contracts(self) -> None:
        text = "define foo.bar\n  takes: url: text"
        assert _annotate_manifest(text, {}) == text

    def test_forced_param_hidden(self) -> None:
        text = "define foo.bar\n  api_key: text\n  url: text"
        contracts = {"bar": {"api_key": "secret123"}}
        result = _annotate_manifest(text, contracts)
        assert "api_key" not in result
        assert "url" in result

    def test_dynamic_param_annotated(self) -> None:
        text = "define foo.bar\n  url: text"
        contracts = {"bar": {"url": "https://example.com/*"}}
        result = _annotate_manifest(text, contracts)
        assert "[contract:" in result


class TestCLIMain:
    def test_main_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        old_argv = sys.argv
        sys.argv = ["lumon", "--help"]
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert "lumon" in captured.out.lower()

    def test_main_version_subcommand(self, capsys: pytest.CaptureFixture[str]) -> None:
        old_argv = sys.argv
        sys.argv = ["lumon", "version"]
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert "lumon" in captured.out.lower()

    def test_main_inline_code(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "return 42"]
        os.chdir(str(tmp_path))
        try:
            with patch("lumon.cli._STATE_FILE", state_file):
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "42" in captured.out

    def test_main_spec_subcommand(self, capsys: pytest.CaptureFixture[str]) -> None:
        old_argv = sys.argv
        sys.argv = ["lumon", "spec"]
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert len(captured.out) > 100

    def test_main_browse_subcommand(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "browse"]
        os.chdir(str(tmp_path))
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "io" in captured.out

    def test_main_file_path(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        lumon_file = os.path.join(root, "test.lumon")
        with open(lumon_file, "w", encoding="utf-8") as f:
            f.write("return 99\n")
        state_file = Path(root) / ".lumon_state.json"
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", lumon_file]
        os.chdir(root)
        try:
            with patch("lumon.cli._STATE_FILE", state_file):
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "99" in captured.out

    def test_main_test_subcommand(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "test"]
        os.chdir(str(tmp_path))
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "No tests found" in captured.out

    def test_main_respond_subcommand(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "respond", '"hello"']
        os.chdir(str(tmp_path))
        try:
            with patch("lumon.cli._STATE_FILE", state_file):
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "no suspended execution" in captured.err

    def test_main_deploy_subcommand(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        target = os.path.join(str(tmp_path), "proj")
        os.makedirs(target)
        old_argv = sys.argv
        sys.argv = ["lumon", "deploy", target]
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert "Deployed" in captured.out


class TestApplyWorkingDir:
    def test_working_dir_flag(self, tmp_path: object) -> None:
        from lumon.cli import _apply_working_dir

        assert isinstance(tmp_path, os.PathLike)
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "--working-dir", str(tmp_path), "return 1"]
        try:
            _apply_working_dir()
            assert os.getcwd() == str(tmp_path)
            assert "--working-dir" not in sys.argv
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)

    def test_working_dir_equals_flag(self, tmp_path: object) -> None:
        from lumon.cli import _apply_working_dir

        assert isinstance(tmp_path, os.PathLike)
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", f"--working-dir={tmp_path}", "return 1"]
        try:
            _apply_working_dir()
            assert os.getcwd() == str(tmp_path)
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)


class TestCmdRunCodeResume:
    def test_resume_same_code(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Line 83: state exists with same code — responses are deserialized."""
        assert isinstance(tmp_path, os.PathLike)
        state_file = Path(str(tmp_path)) / ".lumon_state.json"
        code = 'let x = ask\n  "what?"\nreturn x'
        with patch("lumon.cli._STATE_FILE", state_file):
            _save_state(code, ['"hello"'])
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                result = cmd_run_code(code)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"


class TestAnnotateManifestEdgeCases:
    def test_non_dict_fn_contracts_skipped(self) -> None:
        """Line 158: fn_contracts is not a dict — skip."""
        text = "define foo.bar\n  url: text"
        contracts = {"bar": "not_a_dict"}
        result = _annotate_manifest(text, contracts)
        assert result == text
