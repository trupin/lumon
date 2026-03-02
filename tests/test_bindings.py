"""Tests for Lumon bindings: let, shadowing, immutability, namespace separation."""

import pytest


@pytest.fixture
def run(runner):
    def _run(code):
        return runner.run(code)
    return _run


class TestLetBindings:
    def test_basic_let(self, run):
        r = run("let x = 42\nreturn x")
        assert r.value == 42

    def test_text_binding(self, run):
        r = run('let name = "Lumon"\nreturn name')
        assert r.value == "Lumon"

    def test_list_binding(self, run):
        r = run("let items = [1, 2, 3]\nreturn items")
        assert r.value == [1, 2, 3]

    def test_map_binding(self, run):
        r = run('let user = {name: "Theo"}\nreturn user')
        assert r.value == {"name": "Theo"}

    def test_multiple_bindings(self, run):
        r = run("let a = 1\nlet b = 2\nlet c = 3\nreturn [a, b, c]")
        assert r.value == [1, 2, 3]

    def test_binding_from_expression(self, run):
        r = run("let x = 2 + 3\nreturn x")
        assert r.value == 5


class TestShadowing:
    def test_simple_shadow(self, run):
        r = run("let x = 1\nlet x = 2\nreturn x")
        assert r.value == 2

    def test_shadow_uses_previous_value(self, run):
        r = run("let x = 1\nlet x = x + 1\nreturn x")
        assert r.value == 2

    def test_shadow_changes_type(self, run):
        """Shadowing can change the type of a binding."""
        r = run('let x = 42\nlet x = "now text"\nreturn x')
        assert r.value == "now text"

    def test_multiple_shadows(self, run):
        r = run("let x = 1\nlet x = x + 1\nlet x = x * 3\nreturn x")
        assert r.value == 6


class TestNamespaceVariableSeparation:
    def test_variable_named_text_doesnt_shadow_namespace(self, run):
        """A variable named 'text' does not shadow the text namespace."""
        r = run('let text = "hello"\nreturn text.length(text)')
        assert r.value == 5

    def test_variable_named_list_doesnt_shadow_namespace(self, run):
        r = run("let list = [1, 2, 3]\nreturn list.length(list)")
        assert r.value == 3
