"""Tests for implement/define persistence across invocations."""

import os
import tempfile

import pytest

from lumon.interpreter import interpret
from tests.conftest import RunResult


class TestPersistence:
    def test_implement_block_saved_to_impl(self):
        """Running implement block with persist=True saves to lumon/impl/."""
        with tempfile.TemporaryDirectory() as wd:
            code = (
                'define math.double\n'
                '  "Double a number"\n'
                '  takes:\n'
                '    n: number "The number"\n'
                '  returns: number "The doubled number"\n'
                '\n'
                'implement math.double\n'
                '  return n * 2\n'
                '\n'
                'return math.double(21)'
            )
            result = interpret(code, working_dir=wd, persist=True)
            assert result == {"type": "result", "value": 42}

            impl_path = os.path.join(wd, "lumon", "impl", "math.lumon")
            assert os.path.isfile(impl_path)
            content = open(impl_path, encoding="utf-8").read()
            assert "implement math.double" in content
            assert "return n * 2" in content

    def test_define_block_saved_to_manifests(self):
        """Running define block with persist=True saves to lumon/manifests/."""
        with tempfile.TemporaryDirectory() as wd:
            code = (
                'define math.double\n'
                '  "Double a number"\n'
                '  takes:\n'
                '    n: number "The number"\n'
                '  returns: number "The doubled number"\n'
                '\n'
                'implement math.double\n'
                '  return n * 2\n'
                '\n'
                'return math.double(21)'
            )
            result = interpret(code, working_dir=wd, persist=True)
            assert result == {"type": "result", "value": 42}

            manifest_path = os.path.join(wd, "lumon", "manifests", "math.lumon")
            assert os.path.isfile(manifest_path)
            content = open(manifest_path, encoding="utf-8").read()
            assert "define math.double" in content
            assert '"Double a number"' in content

    def test_persisted_function_callable_in_next_invocation(self):
        """Round-trip: persist in first invocation, auto-load in second."""
        with tempfile.TemporaryDirectory() as wd:
            # First invocation: define + implement + persist
            code1 = (
                'define calc.triple\n'
                '  "Triple a number"\n'
                '  takes:\n'
                '    n: number "The number"\n'
                '  returns: number "Tripled"\n'
                '\n'
                'implement calc.triple\n'
                '  return n * 3\n'
                '\n'
                'return calc.triple(10)'
            )
            r1 = interpret(code1, working_dir=wd, persist=True)
            assert r1 == {"type": "result", "value": 30}

            # Second invocation: just call the function (auto-loaded from disk)
            code2 = 'return calc.triple(7)'
            r2 = interpret(code2, working_dir=wd)
            assert r2 == {"type": "result", "value": 21}

    def test_existing_block_replaced_on_reimplementation(self):
        """Re-implementing a function replaces the old block on disk."""
        with tempfile.TemporaryDirectory() as wd:
            # First version
            code1 = (
                'define math.op\n'
                '  "An operation"\n'
                '  takes:\n'
                '    n: number "Number"\n'
                '  returns: number "Result"\n'
                '\n'
                'implement math.op\n'
                '  return n + 1\n'
                '\n'
                'return math.op(5)'
            )
            r1 = interpret(code1, working_dir=wd, persist=True)
            assert r1 == {"type": "result", "value": 6}

            # Second version (different implementation)
            code2 = (
                'define math.op\n'
                '  "An operation"\n'
                '  takes:\n'
                '    n: number "Number"\n'
                '  returns: number "Result"\n'
                '\n'
                'implement math.op\n'
                '  return n * 10\n'
                '\n'
                'return math.op(5)'
            )
            r2 = interpret(code2, working_dir=wd, persist=True)
            assert r2 == {"type": "result", "value": 50}

            # Verify the file was updated
            impl_path = os.path.join(wd, "lumon", "impl", "math.lumon")
            content = open(impl_path, encoding="utf-8").read()
            assert "return n * 10" in content
            assert "return n + 1" not in content

    def test_builtin_namespaces_not_persisted(self):
        """Builtin namespaces (text, list, etc.) are never persisted."""
        with tempfile.TemporaryDirectory() as wd:
            code = 'return list.map([1, 2], fn(x) -> x * 2)'
            interpret(code, working_dir=wd, persist=True)

            impl_dir = os.path.join(wd, "lumon", "impl")
            manifest_dir = os.path.join(wd, "lumon", "manifests")
            # Neither directory should exist since there are no user blocks
            assert not os.path.exists(impl_dir) or not os.listdir(impl_dir)
            assert not os.path.exists(manifest_dir) or not os.listdir(manifest_dir)
