"""Tests for Lumon types: literals, truthy/falsy, parameterized lists,
structural maps, tags, and value serialization."""

from tests.conftest import LumonRunner

import pytest


@pytest.fixture
def run(runner):
    """Shortcut: run code and return the result value."""
    def _run(code):
        return runner.run(code)
    return _run


# ===================================================================
# Text literals
# ===================================================================

class TestTextLiterals:
    def test_simple_string(self, run):
        r = run('return "hello"')
        assert r.value == "hello"

    def test_empty_string(self, run):
        r = run('return ""')
        assert r.value == ""

    def test_string_with_spaces(self, run):
        r = run('return "hello world"')
        assert r.value == "hello world"

    def test_escape_newline(self, run):
        r = run(r'return "line1\nline2"')
        assert r.value == "line1\nline2"

    def test_escape_tab(self, run):
        r = run(r'return "col1\tcol2"')
        assert r.value == "col1\tcol2"

    def test_escape_backslash(self, run):
        r = run(r'return "back\\slash"')
        assert r.value == "back\\slash"

    def test_escape_quote(self, run):
        r = run(r'return "say \"hi\""')
        assert r.value == 'say "hi"'

    def test_interpolation_variable(self, run):
        r = run('let name = "Lumon"\nreturn "hi \\(name)"')
        assert r.value == "hi Lumon"

    def test_interpolation_expression(self, run):
        r = run('let n = 3\nreturn "\\(n * 2) items"')
        assert r.value == "6 items"

    def test_interpolation_calls_text_from(self, run):
        r = run('let n = 42\nreturn "value: \\(n)"')
        assert r.value == "value: 42"


# ===================================================================
# Number literals
# ===================================================================

class TestNumberLiterals:
    def test_integer(self, run):
        r = run("return 42")
        assert r.value == 42

    def test_float(self, run):
        r = run("return 3.14")
        assert r.value == pytest.approx(3.14)

    def test_negative_integer(self, run):
        r = run("return -1")
        assert r.value == -1

    def test_zero(self, run):
        r = run("return 0")
        assert r.value == 0

    def test_negative_float(self, run):
        r = run("return -0.5")
        assert r.value == pytest.approx(-0.5)


# ===================================================================
# Bool literals
# ===================================================================

class TestBoolLiterals:
    def test_true(self, run):
        r = run("return true")
        assert r.value is True

    def test_false(self, run):
        r = run("return false")
        assert r.value is False


# ===================================================================
# None literal
# ===================================================================

class TestNoneLiteral:
    def test_none(self, run):
        r = run("return none")
        assert r.value is None


# ===================================================================
# List literals
# ===================================================================

class TestListLiterals:
    def test_number_list(self, run):
        r = run("return [1, 2, 3]")
        assert r.value == [1, 2, 3]

    def test_text_list(self, run):
        r = run('return ["a", "b", "c"]')
        assert r.value == ["a", "b", "c"]

    def test_empty_list(self, run):
        r = run("return []")
        assert r.value == []

    def test_nested_list(self, run):
        r = run("return [[1, 2], [3, 4]]")
        assert r.value == [[1, 2], [3, 4]]

    def test_single_element(self, run):
        r = run("return [42]")
        assert r.value == [42]


# ===================================================================
# Map literals
# ===================================================================

class TestMapLiterals:
    def test_simple_map(self, run):
        r = run('return {name: "Theo", age: 30}')
        assert r.value == {"name": "Theo", "age": 30}

    def test_empty_map(self, run):
        r = run("return {}")
        assert r.value == {}

    def test_nested_map(self, run):
        r = run('return {user: {name: "Theo"}}')
        assert r.value == {"user": {"name": "Theo"}}

    def test_map_keys_are_text(self, run):
        """Map literal keys are bare identifiers interpreted as text strings."""
        r = run('return {name: "Theo"}')
        assert "name" in r.value
        assert isinstance(list(r.value.keys())[0], str)


# ===================================================================
# Tag literals and serialization
# ===================================================================

class TestTagLiterals:
    def test_bare_tag(self, run):
        r = run("return :ok")
        assert r.value == {"tag": "ok"}

    def test_tag_with_text_payload(self, run):
        r = run('return :error("not found")')
        assert r.value == {"tag": "error", "value": "not found"}

    def test_tag_with_number_payload(self, run):
        r = run("return :count(42)")
        assert r.value == {"tag": "count", "value": 42}

    def test_tag_with_map_payload(self, run):
        r = run("return :error({code: 404})")
        assert r.value == {"tag": "error", "value": {"code": 404}}

    def test_tag_with_list_payload(self, run):
        r = run("return :items([1, 2, 3])")
        assert r.value == {"tag": "items", "value": [1, 2, 3]}

    def test_tag_stored_in_binding(self, run):
        r = run("let s = :ok\nreturn s")
        assert r.value == {"tag": "ok"}

    def test_tags_in_list(self, run):
        r = run("return [:red, :green, :blue]")
        assert r.value == [{"tag": "red"}, {"tag": "green"}, {"tag": "blue"}]

    def test_tag_with_nested_tag_payload(self, run):
        r = run("return :wrapped(:inner)")
        assert r.value == {"tag": "wrapped", "value": {"tag": "inner"}}


# ===================================================================
# Truthy / falsy
# ===================================================================

class TestTruthyFalsy:
    """false, none, 0, "", [], {} are falsy. Everything else is truthy."""

    def test_false_is_falsy(self, run):
        r = run('return if false "yes" else "no"')
        assert r.value == "no"

    def test_none_is_falsy(self, run):
        r = run('return if none "yes" else "no"')
        assert r.value == "no"

    def test_zero_is_falsy(self, run):
        r = run('return if 0 "yes" else "no"')
        assert r.value == "no"

    def test_empty_string_is_falsy(self, run):
        r = run('return if "" "yes" else "no"')
        assert r.value == "no"

    def test_empty_list_is_falsy(self, run):
        r = run('return if [] "yes" else "no"')
        assert r.value == "no"

    def test_empty_map_is_falsy(self, run):
        r = run('return if {} "yes" else "no"')
        assert r.value == "no"

    def test_true_is_truthy(self, run):
        r = run('return if true "yes" else "no"')
        assert r.value == "yes"

    def test_nonzero_is_truthy(self, run):
        r = run('return if 1 "yes" else "no"')
        assert r.value == "yes"

    def test_nonempty_string_is_truthy(self, run):
        r = run('return if "a" "yes" else "no"')
        assert r.value == "yes"

    def test_nonempty_list_is_truthy(self, run):
        r = run('return if [1] "yes" else "no"')
        assert r.value == "yes"

    def test_nonempty_map_is_truthy(self, run):
        r = run('return if {a: 1} "yes" else "no"')
        assert r.value == "yes"

    def test_tag_is_truthy(self, run):
        r = run('return if :ok "yes" else "no"')
        assert r.value == "yes"


# ===================================================================
# Structural map features
# ===================================================================

class TestStructuralMaps:
    def test_field_access(self, run):
        r = run('let m = {name: "Theo", age: 30}\nreturn m.name')
        assert r.value == "Theo"

    def test_nested_field_access(self, run):
        r = run('let m = {user: {name: "Theo"}}\nreturn m.user.name')
        assert r.value == "Theo"

    def test_spread_adds_field(self, run):
        r = run(
            'let user = {name: "Theo", age: 30}\n'
            'let extended = {...user, email: "t@e.com"}\n'
            "return extended"
        )
        assert r.value == {"name": "Theo", "age": 30, "email": "t@e.com"}

    def test_spread_overrides_field(self, run):
        r = run(
            "let m = {a: 1, b: 2}\n"
            "let m2 = {...m, b: 99}\n"
            "return m2"
        )
        assert r.value == {"a": 1, "b": 99}

    def test_spread_preserves_original(self, run):
        r = run(
            "let m = {a: 1, b: 2}\n"
            "let m2 = {...m, c: 3}\n"
            "return m"
        )
        assert r.value == {"a": 1, "b": 2}


# ===================================================================
# Value serialization (output protocol)
# ===================================================================

class TestValueSerialization:
    """Verify that Lumon values are serialized to JSON correctly."""

    def test_text_to_json_string(self, run):
        r = run('return "hello"')
        assert r.type == "result"
        assert isinstance(r.value, str)

    def test_number_to_json_number(self, run):
        r = run("return 42")
        assert r.type == "result"
        assert isinstance(r.value, (int, float))

    def test_bool_to_json_bool(self, run):
        r = run("return true")
        assert r.type == "result"
        assert isinstance(r.value, bool)

    def test_none_to_json_null(self, run):
        r = run("return none")
        assert r.type == "result"
        assert r.value is None

    def test_list_to_json_array(self, run):
        r = run("return [1, 2, 3]")
        assert r.type == "result"
        assert isinstance(r.value, list)

    def test_map_to_json_object(self, run):
        r = run('return {a: "b"}')
        assert r.type == "result"
        assert isinstance(r.value, dict)

    def test_tag_no_payload_to_json(self, run):
        r = run("return :ok")
        assert r.value == {"tag": "ok"}

    def test_tag_with_payload_to_json(self, run):
        r = run('return :error("fail")')
        assert r.value == {"tag": "error", "value": "fail"}


# ===================================================================
# String interpolation with various types
# ===================================================================


class TestInterpolation:
    def test_interpolate_none(self, run):
        r = run('let x = none\nreturn "val: \\(x)"')
        assert r.value == "val: none"

    def test_interpolate_true(self, run):
        r = run('return "val: \\(true)"')
        assert r.value == "val: true"

    def test_interpolate_false(self, run):
        r = run('return "val: \\(false)"')
        assert r.value == "val: false"

    def test_interpolate_float(self, run):
        r = run('return "val: \\(1.5)"')
        assert r.value == "val: 1.5"

    def test_interpolate_float_whole(self, run):
        r = run('return "val: \\(2.0)"')
        assert r.value == "val: 2"

    def test_interpolate_list(self, run):
        r = run('let xs = [1, 2, 3]\nreturn "val: \\(xs)"')
        assert r.value == "val: [1, 2, 3]"

    def test_interpolate_map(self, run):
        r = run('let m = {a: 1}\nreturn "val: \\(m)"')
        assert r.value == "val: {a: 1}"

    def test_interpolate_tag_no_payload(self, run):
        r = run('let t = :ok\nreturn "val: \\(t)"')
        assert r.value == "val: :ok"

    def test_interpolate_tag_with_payload(self, run):
        r = run('let t = :ok("yes")\nreturn "val: \\(t)"')
        assert r.value == "val: :ok(yes)"


# ===================================================================
# Index access error paths
# ===================================================================


class TestIndexAccessErrors:
    def test_index_out_of_bounds(self, run):
        r = run("return [1, 2, 3][10]")
        assert r.type == "error"

    def test_index_non_list(self, run):
        r = run("let x = 42\nreturn x[0]")
        assert r.type == "error"


# ===================================================================
# Spread on non-map
# ===================================================================


class TestSpreadError:
    def test_spread_non_map(self, run):
        r = run("let x = 42\nreturn {...x}")
        assert r.type == "error"


# ===================================================================
# Field access errors
# ===================================================================


class TestFieldAccessErrors:
    def test_field_access_non_map(self, run):
        r = run("let s = 42\nreturn s.length")
        assert r.type == "error"

    def test_field_access_missing_key(self, run):
        r = run("return {a: 1}.b")
        assert r.type == "error"


# ===================================================================
# Multiline string literals (triple-quoted)
# ===================================================================


class TestMultilineStrings:
    def test_basic_multiline(self, run):
        code = 'return """\nhello\nworld\n"""'
        r = run(code)
        assert r.value == "hello\nworld"

    def test_multiline_with_interpolation(self, run):
        code = 'let name = "Lumon"\nreturn """\nhello \\(name)\n"""'
        r = run(code)
        assert r.value == "hello Lumon"

    def test_multiline_dedent(self, run):
        code = 'return """\n    line1\n    line2\n    """'
        r = run(code)
        assert r.value == "line1\nline2"

    def test_multiline_empty(self, run):
        r = run('return """"""')
        assert r.value == ""

    def test_multiline_internal_quotes(self, run):
        code = 'return """\nsay "hi" and ""ok""\n"""'
        r = run(code)
        assert r.value == 'say "hi" and ""ok""'

    def test_multiline_preserves_comments(self, run):
        code = 'return """\n-- this is not a comment\n"""'
        r = run(code)
        assert r.value == "-- this is not a comment"

    def test_multiline_escape_sequences(self, run):
        code = 'return """\ncol1\\tcol2\n"""'
        r = run(code)
        assert r.value == "col1\tcol2"

    def test_multiline_in_pattern(self, run):
        code = (
            'let x = "hello\\nworld"\n'
            'return match x\n'
            '  """\n'
            '  hello\n'
            '  world\n'
            '  """ -> "matched"\n'
            '  _ -> "nope"'
        )
        r = run(code)
        assert r.value == "matched"

    def test_multiline_inline(self, run):
        """Triple-quoted string on one line."""
        r = run('return """hello"""')
        assert r.value == "hello"

    def test_multiline_dedent_mixed_indent(self, run):
        code = 'return """\n    line1\n      line2\n    """'
        r = run(code)
        assert r.value == "line1\n  line2"

    def test_multiline_in_ask(self, run):
        code = (
            'let decision = ask\n'
            '  """\n'
            '  Which item\n'
            '  should go first?\n'
            '  """\n'
            '  context: [1, 2, 3]\n'
        )
        r = run(code)
        assert r.type == "ask"
        assert r.output["prompt"] == "Which item\nshould go first?"

    def test_multiline_preserves_pipe_lines(self, run):
        code = 'return """\n|> not a pipe\n"""'
        r = run(code)
        assert r.value == "|> not a pipe"

    def test_multiline_interpolation_with_call(self, run):
        code = 'let xs = [1, 2]\nreturn """\ncount: \\(list.length(xs))\n"""'
        r = run(code)
        assert r.value == "count: 2"

    def test_multiline_unclosed_is_error(self, run):
        r = run('return """hello')
        assert r.type == "error"
