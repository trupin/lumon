"""Unit tests for lumon.cli — testing CLI functions directly in pytest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from unittest.mock import patch

import pytest

from lumon.cli import (
    _annotate_manifest,
    _bundled_manifest,
    _clear_state,
    _COMM_BASE,
    _comm_dir_for_session,
    _deploy_plugin_skills,
    _deploy_skills,
    _find_pending_daemon,
    _find_session,
    _format_contract,
    _prompt_overwrite,
    _save_script_marker,
    cmd_browse,
    cmd_deploy,
    cmd_respond,
    cmd_run_code,
    cmd_spec,
    cmd_test,
    cmd_version,
    main,
)
from lumon.daemon import is_daemon_alive


class TestSessionHelpers:
    def test_save_script_marker(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = os.path.join(str(tmp_path), ".lumon_comm", "abc12345")
        _save_script_marker(comm_dir, "test.lumon")
        marker = os.path.join(comm_dir, "script.txt")
        assert os.path.isfile(marker)
        with open(marker, encoding="utf-8") as f:
            assert f.read() == "test.lumon"

    def test_clear_state(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        comm_dir = os.path.join(comm_base, "abc12345")
        os.makedirs(comm_dir)
        with open(os.path.join(comm_dir, "script.txt"), "w") as f:
            f.write("test.lumon")
        with patch("lumon.cli._COMM_BASE", comm_base):
            _clear_state("abc12345")
        assert not os.path.isdir(comm_dir)

    def test_clear_state_kills_daemon(self, tmp_path: object) -> None:
        """_clear_state calls _kill_daemon when PID file exists."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        comm_dir = os.path.join(comm_base, "abc12345")
        os.makedirs(comm_dir)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("99999")
        with patch("lumon.cli._COMM_BASE", comm_base), \
             patch("lumon.cli._kill_daemon") as mock_kill:
            _clear_state("abc12345")
            mock_kill.assert_called_once_with(comm_dir)

    def test_clear_state_noop_if_missing(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            _clear_state("nonexistent")  # should not raise

    def test_find_session(self, tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            assert _find_session() is None
            comm_dir = os.path.join(comm_base, "abc12345")
            os.makedirs(comm_dir)
            assert _find_session() == "abc12345"


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
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
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
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                result = cmd_run_code("return undefined_var")
            finally:
                os.chdir(old_cwd)
        assert result == 1

    def test_ask_creates_session(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                cmd_run_code('let x = ask\n  "what?"')
            finally:
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "ask"
        assert "session" in output
        # A session directory should exist
        assert os.path.isdir(comm_base)
        sessions = os.listdir(comm_base)
        assert len(sessions) == 1
        # Wait briefly for daemon to write pid, then clean up
        import time
        time.sleep(0.3)
        with patch("lumon.cli._COMM_BASE", comm_base):
            _clear_state(sessions[0])


class TestCmdRespond:
    def test_no_state_error(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session=None)
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "no suspended execution" in captured.err

    def test_dead_daemon_error(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Respond errors if daemon is dead."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        comm_dir = os.path.join(comm_base, "abc12345")
        os.makedirs(comm_dir)
        # Write a PID that doesn't exist
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("999999999")
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session="abc12345", clear=False)
            result = cmd_respond(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "not running" in captured.err

    def test_respond_full_cycle(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Full ask → respond cycle using daemon model."""
        import time
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                # Step 1: Run code that asks
                capsys.readouterr()
                cmd_run_code('let x = ask\n  "what?"\nreturn x')
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                assert first_output["type"] == "ask"
                session = first_output["session"]

                # Step 2: Write response file
                comm_dir = _comm_dir_for_session(session)
                response_file = os.path.join(comm_dir, "ask_response.json")
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump("the answer", f)

                # Step 3: Respond — daemon should pick up response
                capsys.readouterr()
                args = argparse.Namespace(session=session, clear=False)
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "the answer"


class TestRespondDaemon:
    def test_respond_full_ask_cycle(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Full ask → respond cycle using daemon model."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                # Step 1: Run code that asks
                capsys.readouterr()
                cmd_run_code('let x = ask\n  "what?"\nreturn x')
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                assert first_output["type"] == "ask"
                session = first_output["session"]

                # Step 2: Write response file
                comm_dir = _comm_dir_for_session(session)
                response_file = os.path.join(comm_dir, "ask_response.json")
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump("the answer", f)

                # Step 3: Respond
                capsys.readouterr()
                args = argparse.Namespace(session=session, clear=False)
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == "the answer"

    def test_respond_spawn_batch_cycle(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Full spawn → respond cycle using daemon model."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        code = 'let a = spawn\n  "Task A"\nlet b = spawn\n  "Task B"\nreturn [a, b]'
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                capsys.readouterr()
                cmd_run_code(code)
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                assert first_output["type"] == "spawn_batch"
                session = first_output["session"]

                # Write spawn response files
                comm_dir = _comm_dir_for_session(session)
                for i, resp in enumerate(["resp A", "resp B"]):
                    resp_file = os.path.join(comm_dir, f"spawn_{i}_response.json")
                    with open(resp_file, "w", encoding="utf-8") as f:
                        json.dump(resp, f)

                capsys.readouterr()
                args = argparse.Namespace(session=session, clear=False)
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == ["resp A", "resp B"]

    def test_respond_unwraps_spawn_wrapper(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Spawn responses with {result: ..., spawn_id: N} wrappers are unwrapped."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        code = 'let a = spawn\n  "Task A"\nlet b = spawn\n  "Task B"\nreturn [a, b]'
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                capsys.readouterr()
                cmd_run_code(code)
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                session = first_output["session"]

                comm_dir = _comm_dir_for_session(session)
                for i, resp in enumerate([{"result": "A", "spawn_id": 0}, {"result": "B", "spawn_id": 1}]):
                    resp_file = os.path.join(comm_dir, f"spawn_{i}_response.json")
                    with open(resp_file, "w", encoding="utf-8") as f:
                        json.dump(resp, f)

                capsys.readouterr()
                args = argparse.Namespace(session=session, clear=False)
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == ["A", "B"]

    def test_respond_cleans_up_after_result(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """After successful respond, the session comm directory is cleaned up."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                capsys.readouterr()
                cmd_run_code('let x = ask\n  "what?"\nreturn x')
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                session = first_output["session"]
                comm_dir = _comm_dir_for_session(session)

                response_file = os.path.join(comm_dir, "ask_response.json")
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump("done", f)

                capsys.readouterr()
                args = argparse.Namespace(session=session, clear=False)
                cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        # Session directory should be cleaned up
        assert not os.path.isdir(comm_dir)

    def test_respond_auto_detects_session(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """When session is not specified, auto-detect the single active session."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                capsys.readouterr()
                cmd_run_code('let x = ask\n  "what?"\nreturn x')
                captured = capsys.readouterr()
                first_output = json.loads(captured.out)
                session = first_output["session"]

                comm_dir = _comm_dir_for_session(session)
                response_file = os.path.join(comm_dir, "ask_response.json")
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump("auto", f)

                capsys.readouterr()
                args = argparse.Namespace(session=None, clear=False)
                result = cmd_respond(args)
            finally:
                os.chdir(old_cwd)
        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["value"] == "auto"


    def test_respond_reads_output_when_daemon_already_finished(
        self, capsys: pytest.CaptureFixture[str], tmp_path: object,
    ) -> None:
        """respond reads output.json even if the daemon has already exited."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        session = "deadbeef"
        comm_dir = os.path.join(comm_base, session)
        os.makedirs(comm_dir)

        # Simulate daemon that already completed: pid file with dead PID, output.json present
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("999999999")  # dead PID
        with open(os.path.join(comm_dir, "output.json"), "w") as f:
            json.dump({"type": "result", "value": ["spawn_result"]}, f)

        with patch("lumon.cli._COMM_BASE", comm_base):
            capsys.readouterr()
            args = argparse.Namespace(session=session, clear=False)
            result = cmd_respond(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == ["spawn_result"]
        # Session should be cleaned up after completion
        assert not os.path.isdir(comm_dir)


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
        assert sorted(skills.keys()) == ["ask-spawn", "auto-deploy", "code-organization", "issues", "lumon", "plugins-issues", "review", "version-control", "workflow"]
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
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "return 42"]
        os.chdir(str(tmp_path))
        try:
            with patch("lumon.cli._COMM_BASE", comm_base):
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
        comm_base = os.path.join(root, ".lumon_comm")
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", lumon_file]
        os.chdir(root)
        try:
            with patch("lumon.cli._COMM_BASE", comm_base):
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "99" in captured.out

    def test_main_file_path_blocked_by_pending_session(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        assert isinstance(tmp_path, os.PathLike)
        root = str(tmp_path)
        lumon_file = os.path.join(root, "test.lumon")
        with open(lumon_file, "w", encoding="utf-8") as f:
            f.write('let x = ask\n  "q"\nreturn x\n')
        comm_base = os.path.join(root, ".lumon_comm")
        old_argv = sys.argv
        old_cwd = os.getcwd()
        os.chdir(root)
        try:
            with patch("lumon.cli._COMM_BASE", comm_base):
                # Create a pending daemon session for this script
                comm_dir = os.path.join(comm_base, "sess1234")
                os.makedirs(comm_dir)
                _save_script_marker(comm_dir, lumon_file)
                # Write current PID as daemon (it's alive)
                with open(os.path.join(comm_dir, "pid"), "w") as f:
                    f.write(str(os.getpid()))
                sys.argv = ["lumon", lumon_file]
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
            # Clean up fake session (don't use _clear_state as it tries to kill our PID)
            import shutil
            fake_dir = os.path.join(comm_base, "sess1234")
            if os.path.isdir(fake_dir):
                shutil.rmtree(fake_dir)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "error"
        assert "pending session" in output["message"]

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
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        old_argv = sys.argv
        old_cwd = os.getcwd()
        sys.argv = ["lumon", "respond"]
        os.chdir(str(tmp_path))
        try:
            with patch("lumon.cli._COMM_BASE", comm_base):
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


class TestCmdRunCodeCleanup:
    def test_fresh_run_does_not_clean_live_sessions(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """A fresh cmd_run_code does not remove live daemon sessions."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        # Create a session with current PID (alive)
        other_dir = os.path.join(comm_base, "other123")
        os.makedirs(other_dir)
        with open(os.path.join(other_dir, "pid"), "w") as f:
            f.write(str(os.getpid()))
        with patch("lumon.cli._COMM_BASE", comm_base):
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                cmd_run_code("return 42")
            finally:
                os.chdir(old_cwd)
        # Other session should still exist (daemon is alive)
        assert os.path.isdir(other_dir)


class TestAnnotateManifestEdgeCases:
    def test_non_dict_fn_contracts_skipped(self) -> None:
        """Line 158: fn_contracts is not a dict — skip."""
        text = "define foo.bar\n  url: text"
        contracts = {"bar": "not_a_dict"}
        result = _annotate_manifest(text, contracts)
        assert result == text


class TestPendingSessionDetection:
    def _make_fake_daemon(self, comm_base: str, session: str, script: str) -> None:
        """Create a fake daemon session with the current process PID."""
        comm_dir = os.path.join(comm_base, session)
        os.makedirs(comm_dir, exist_ok=True)
        _save_script_marker(comm_dir, script)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write(str(os.getpid()))

    def test_rerun_blocked_by_pending_session(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Running the same script with a pending daemon returns an error."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            self._make_fake_daemon(comm_base, "sess1234", "test.lumon")
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                exit_code = cmd_run_code('return ask("q")', script="test.lumon")
            finally:
                os.chdir(old_cwd)
        assert exit_code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "error"
        assert "pending session" in output["message"]
        assert "lumon respond" in output["message"]

    def test_rerun_allowed_for_different_script(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Running a different script is not blocked by another script's pending session."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            self._make_fake_daemon(comm_base, "sess1234", "other.lumon")
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                exit_code = cmd_run_code("return 42", script="test.lumon")
            finally:
                os.chdir(old_cwd)
        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert output["value"] == 42

    def test_rerun_allowed_for_inline_code(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """Inline code (no script) is not blocked by pending sessions."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            self._make_fake_daemon(comm_base, "sess1234", "test.lumon")
            old_cwd = os.getcwd()
            os.chdir(str(tmp_path))
            try:
                exit_code = cmd_run_code("return 42")
            finally:
                os.chdir(old_cwd)
        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"


class TestRespondClear:
    def test_respond_clear_removes_session(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """--clear removes a pending session."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        comm_dir = os.path.join(comm_base, "sess1234")
        os.makedirs(comm_dir)
        with open(os.path.join(comm_dir, "pid"), "w") as f:
            f.write("999999999")  # non-existent PID
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session="sess1234", clear=True)
            exit_code = cmd_respond(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert "cleared" in output["value"]
        assert not os.path.isdir(comm_dir)

    def test_respond_clear_auto_detect(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """--clear without session ID auto-detects the single active session."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        comm_dir = os.path.join(comm_base, "sess1234")
        os.makedirs(comm_dir)
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session=None, clear=True)
            exit_code = cmd_respond(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["type"] == "result"
        assert "sess1234" in output["value"]

    def test_respond_clear_specific_session_with_multiple(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """--clear with explicit session ID only clears that session."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        for sess in ("sess_a", "sess_b"):
            d = os.path.join(comm_base, sess)
            os.makedirs(d)
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session="sess_a", clear=True)
            exit_code = cmd_respond(args)
        assert exit_code == 0
        assert not os.path.isdir(os.path.join(comm_base, "sess_a"))
        assert os.path.isdir(os.path.join(comm_base, "sess_b"))

    def test_respond_clear_no_session_error(self, capsys: pytest.CaptureFixture[str], tmp_path: object) -> None:
        """--clear with no sessions returns an error."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            args = argparse.Namespace(session=None, clear=True)
            exit_code = cmd_respond(args)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "no pending session" in captured.err


class TestScriptMarker:
    def test_script_marker_saved(self, tmp_path: object) -> None:
        """Verify script marker is saved."""
        assert isinstance(tmp_path, os.PathLike)
        comm_dir = os.path.join(str(tmp_path), ".lumon_comm", "sess1234")
        _save_script_marker(comm_dir, "my_script.lumon")
        marker = os.path.join(comm_dir, "script.txt")
        assert os.path.isfile(marker)
        with open(marker, encoding="utf-8") as f:
            assert f.read() == "my_script.lumon"

    def test_find_pending_daemon(self, tmp_path: object) -> None:
        """_find_pending_daemon finds sessions by script with alive daemon."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        for sess, script in [("sess_a", "a.lumon"), ("sess_b", "b.lumon")]:
            d = os.path.join(comm_base, sess)
            os.makedirs(d)
            _save_script_marker(d, script)
            # Use current PID (alive)
            with open(os.path.join(d, "pid"), "w") as f:
                f.write(str(os.getpid()))
        with patch("lumon.cli._COMM_BASE", comm_base):
            assert _find_pending_daemon("a.lumon") == "sess_a"
            assert _find_pending_daemon("b.lumon") == "sess_b"
            assert _find_pending_daemon("c.lumon") is None

    def test_find_pending_daemon_no_comm_dir(self, tmp_path: object) -> None:
        """_find_pending_daemon returns None when .lumon_comm doesn't exist."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        with patch("lumon.cli._COMM_BASE", comm_base):
            assert _find_pending_daemon("test.lumon") is None

    def test_find_pending_daemon_ignores_dead(self, tmp_path: object) -> None:
        """_find_pending_daemon ignores sessions with dead daemon PIDs."""
        assert isinstance(tmp_path, os.PathLike)
        comm_base = os.path.join(str(tmp_path), ".lumon_comm")
        d = os.path.join(comm_base, "sess_dead")
        os.makedirs(d)
        _save_script_marker(d, "test.lumon")
        with open(os.path.join(d, "pid"), "w") as f:
            f.write("999999999")
        with patch("lumon.cli._COMM_BASE", comm_base):
            assert _find_pending_daemon("test.lumon") is None
