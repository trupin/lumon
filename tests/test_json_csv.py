"""Tests for Lumon json.* and csv.* built-ins."""

from __future__ import annotations

import pytest

from tests.conftest import MockFS


@pytest.fixture
def run(runner):
    def _run(code, *, io=None):
        return runner.run(code, io=io)
    return _run


# ===================================================================
# json.parse
# ===================================================================

class TestJsonParse:
    def test_parse_object(self, run):
        # Round-trip: serialize a map to JSON text, then parse it back
        code = """
let s = json.to_text({name: "Alice", age: 30})
return json.parse(s)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value == {"name": "Alice", "age": 30}

    def test_parse_array(self, run):
        r = run("return json.parse(\"[1,2,3]\")")
        assert r.tag_name == "ok"
        assert r.tag_value == [1, 2, 3]

    def test_parse_string(self, run):
        code = """
let s = json.to_text("hello")
return json.parse(s)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value == "hello"

    def test_parse_number(self, run):
        r = run('return json.parse("42")')
        assert r.tag_name == "ok"
        assert r.tag_value == 42

    def test_parse_boolean(self, run):
        r = run('return json.parse("true")')
        assert r.tag_name == "ok"
        assert r.tag_value is True

    def test_parse_null(self, run):
        r = run('return json.parse("null")')
        assert r.tag_name == "ok"
        assert r.tag_value is None

    def test_parse_invalid(self, run):
        r = run('return json.parse("not json")')
        assert r.tag_name == "error"
        assert isinstance(r.tag_value, str)

    def test_parse_empty_string(self, run):
        r = run('return json.parse("")')
        assert r.tag_name == "error"

    def test_parse_nested(self, run):
        code = """
let s = json.to_text({a: {b: [1, 2]}})
return json.parse(s)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value == {"a": {"b": [1, 2]}}

    def test_parse_tag_object(self, run):
        """Tag objects round-trip through JSON as {"tag": "name", "value": ...}."""
        code = """
let s = json.to_text(:ok("done"))
return json.parse(s)
"""
        r = run(code)
        assert r.tag_name == "ok"
        # The inner value is deserialized as a LumonTag :ok("done"),
        # serialized in output as {"tag": "ok", "value": "done"}
        assert r.tag_value == {"tag": "ok", "value": "done"}


# ===================================================================
# json.to_text
# ===================================================================

class TestJsonToText:
    def test_map(self, run):
        r = run('return json.to_text({name: "Alice", age: 30})')
        assert r.value == '{"name":"Alice","age":30}'

    def test_list(self, run):
        r = run("return json.to_text([1, 2, 3])")
        assert r.value == "[1,2,3]"

    def test_string(self, run):
        r = run('return json.to_text("hello")')
        assert r.value == '"hello"'

    def test_number(self, run):
        r = run("return json.to_text(42)")
        assert r.value == "42"

    def test_boolean(self, run):
        r = run("return json.to_text(true)")
        assert r.value == "true"

    def test_none(self, run):
        r = run("return json.to_text(none)")
        assert r.value == "null"

    def test_tag(self, run):
        r = run('return json.to_text(:ok("done"))')
        assert r.value == '{"tag":"ok","value":"done"}'

    def test_tag_no_payload(self, run):
        r = run("return json.to_text(:ok)")
        assert r.value == '{"tag":"ok"}'


# ===================================================================
# json.to_text_pretty
# ===================================================================

class TestJsonToTextPretty:
    def test_indented(self, run):
        r = run('return json.to_text_pretty({name: "Alice"})')
        assert '"name": "Alice"' in r.value
        assert "\n" in r.value


# ===================================================================
# json.read / json.write (sandboxed via io)
# ===================================================================

class TestJsonRead:
    def test_read_valid(self, run):
        fs = MockFS({"data.json": '{"key":"value"}'})
        r = run('return json.read("data.json")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == {"key": "value"}

    def test_read_invalid_json(self, run):
        fs = MockFS({"bad.json": "not json"})
        r = run('return json.read("bad.json")', io=fs)
        assert r.tag_name == "error"

    def test_read_missing_file(self, run):
        fs = MockFS()
        r = run('return json.read("missing.json")', io=fs)
        assert r.tag_name == "error"

    def test_read_path_traversal(self, run):
        fs = MockFS()
        r = run('return json.read("../../etc/passwd")', io=fs)
        assert r.tag_name == "error"


class TestJsonWrite:
    def test_write_and_read_roundtrip(self, run):
        fs = MockFS()
        run('return json.write("out.json", {a: 1, b: [2, 3]})', io=fs)
        r = run('return json.read("out.json")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == {"a": 1, "b": [2, 3]}

    def test_write_path_traversal(self, run):
        fs = MockFS()
        r = run('return json.write("../outside.json", {a: 1})', io=fs)
        assert r.tag_name == "error"

    def test_write_pretty_and_read(self, run):
        fs = MockFS()
        run('return json.write_pretty("out.json", {x: 42})', io=fs)
        r = run('return json.read("out.json")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == {"x": 42}


# ===================================================================
# csv.parse
# ===================================================================

class TestCsvParse:
    def test_basic(self, run):
        r = run('return csv.parse("a,b\\n1,2")')
        assert r.value == [["a", "b"], ["1", "2"]]

    def test_empty(self, run):
        r = run('return csv.parse("")')
        assert r.value == []

    def test_quoted_fields(self, run):
        r = run(r'return csv.parse("\"a,b\",c\n1,2")')
        assert r.value == [["a,b", "c"], ["1", "2"]]

    def test_single_column(self, run):
        r = run('return csv.parse("a\\nb\\nc")')
        assert r.value == [["a"], ["b"], ["c"]]


# ===================================================================
# csv.parse_with_headers
# ===================================================================

class TestCsvParseWithHeaders:
    def test_basic(self, run):
        r = run('return csv.parse_with_headers("name,age\\nAlice,30\\nBob,25")')
        assert r.value == [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]

    def test_missing_field(self, run):
        """Missing fields become empty string, not None."""
        r = run('return csv.parse_with_headers("a,b\\n1")')
        assert r.value == [{"a": "1", "b": ""}]

    def test_empty(self, run):
        r = run('return csv.parse_with_headers("name,age")')
        assert r.value == []


# ===================================================================
# csv.to_text
# ===================================================================

class TestCsvToText:
    def test_basic(self, run):
        r = run('return csv.to_text([["a", "b"], ["1", "2"]])')
        assert "a,b" in r.value
        assert "1,2" in r.value

    def test_roundtrip(self, run):
        r = run('return csv.parse(csv.to_text([["x", "y"], ["1", "2"]]))')
        assert r.value == [["x", "y"], ["1", "2"]]


# ===================================================================
# csv.to_text_with_headers
# ===================================================================

class TestCsvToTextWithHeaders:
    def test_basic(self, run):
        r = run("""
let headers = ["name", "age"]
let rows = [{name: "Alice", age: "30"}]
return csv.to_text_with_headers(headers, rows)
""")
        assert "name,age" in r.value
        assert "Alice,30" in r.value

    def test_extra_keys_ignored(self, run):
        """Extra keys in rows not in headers are silently ignored."""
        r = run("""
let headers = ["a"]
let rows = [{a: "1", b: "2"}]
return csv.to_text_with_headers(headers, rows)
""")
        assert "a" in r.value
        assert "b" not in r.value.split("\n")[0]  # header line


# ===================================================================
# csv.read / csv.write (sandboxed via io)
# ===================================================================

class TestCsvRead:
    def test_read_basic(self, run):
        fs = MockFS({"data.csv": "a,b\n1,2"})
        r = run('return csv.read("data.csv")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == [["a", "b"], ["1", "2"]]

    def test_read_with_headers(self, run):
        fs = MockFS({"data.csv": "name,age\nAlice,30"})
        r = run('return csv.read_with_headers("data.csv")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == [{"name": "Alice", "age": "30"}]

    def test_read_missing(self, run):
        fs = MockFS()
        r = run('return csv.read("missing.csv")', io=fs)
        assert r.tag_name == "error"

    def test_read_path_traversal(self, run):
        fs = MockFS()
        r = run('return csv.read("../../etc/passwd")', io=fs)
        assert r.tag_name == "error"


class TestCsvWrite:
    def test_write_and_read_roundtrip(self, run):
        fs = MockFS()
        run('return csv.write("out.csv", [["a", "b"], ["1", "2"]])', io=fs)
        r = run('return csv.read("out.csv")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == [["a", "b"], ["1", "2"]]

    def test_write_with_headers_roundtrip(self, run):
        fs = MockFS()
        run("""
let h = ["name", "age"]
let rows = [{name: "Alice", age: "30"}]
return csv.write_with_headers("out.csv", h, rows)
""", io=fs)
        r = run('return csv.read_with_headers("out.csv")', io=fs)
        assert r.tag_name == "ok"
        assert r.tag_value == [{"name": "Alice", "age": "30"}]

    def test_write_path_traversal(self, run):
        fs = MockFS()
        r = run('return csv.write("../outside.csv", [["a"]])', io=fs)
        assert r.tag_name == "error"


# ===================================================================
# json.parse round-trip with json.to_text
# ===================================================================

class TestJsonRoundTrip:
    def test_map_roundtrip(self, run):
        code = """
let original = {name: "test", count: 42, active: true}
let json_str = json.to_text(original)
return json.parse(json_str)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value == {"name": "test", "count": 42, "active": True}

    def test_list_roundtrip(self, run):
        code = """
let original = [1, 2, 3]
let json_str = json.to_text(original)
return json.parse(json_str)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value == [1, 2, 3]

    def test_none_roundtrip(self, run):
        code = """
let json_str = json.to_text(none)
return json.parse(json_str)
"""
        r = run(code)
        assert r.tag_name == "ok"
        assert r.tag_value is None
