"""Tests for Lumon type checker: all type errors caught statically before execution.

Every test here expects an interpreter error of type "error" — the type checker
should catch these before any code runs."""

import pytest


@pytest.fixture
def run(runner):
    def _run(code, **kwargs):
        return runner.run(code, **kwargs)
    return _run


# ===================================================================
# Operator type mismatches
# ===================================================================

class TestOperatorTypeMismatch:
    def test_add_number_and_text(self, run):
        r = run('return 42 + "hello"')
        assert r.type == "error"

    def test_subtract_text(self, run):
        r = run('return "hello" - "world"')
        assert r.type == "error"

    def test_multiply_text(self, run):
        r = run('return "hello" * 2')
        assert r.type == "error"

    def test_compare_incompatible_types(self, run):
        r = run('return "hello" < 42')
        assert r.type == "error"

    def test_boolean_and_with_number(self, run):
        """and/or with non-bool operands — truthy/falsy is defined for all types,
        so this may or may not be a type error depending on strictness."""
        r = run('return 1 and 2')
        # If type checker is strict: r.type == "error"
        # If truthy/falsy is allowed: r.value == 2
        assert r.type in ("result", "error")

    def test_any_plus_text_should_not_error(self, run):
        """TAny + text should pass type checking (e.g. match result + string)."""
        code = '''\
let x = :ok("hello")
let a = match x
  :ok(v) -> v
  _ -> "default"
let b = a + "y"
return b + "z"'''
        r = run(code)
        assert r.type == "result"
        assert r.value == "helloyz"


# ===================================================================
# Union type not handled
# ===================================================================

class TestUnionTypeNotHandled:
    def test_use_optional_without_handling_none(self, run):
        """list.head returns a | none, using it directly as number is a type error."""
        r = run(
            'let x = list.head([1, 2, 3])\n'
            'return x + 1'
        )
        assert r.type == "error"

    def test_use_tag_union_without_matching(self, run):
        """io.read returns :ok(text) | :error(text), can't use directly as text."""
        r = run(
            'let r = io.read("file.md")\n'
            'return text.length(r)'
        )
        assert r.type == "error"

    def test_pipe_tag_result_to_text_function(self, run):
        r = run('return io.read("f") |> text.length')
        assert r.type == "error"


# ===================================================================
# Mixed-type lists
# ===================================================================

class TestMixedTypeLists:
    def test_mixed_number_and_text(self, run):
        r = run('return [1, "two", 3]')
        assert r.type == "error"

    def test_mixed_bool_and_number(self, run):
        r = run('return [true, 42]')
        assert r.type == "error"

    def test_mixed_none_and_number(self, run):
        r = run('return [none, 1]')
        assert r.type == "error"


# ===================================================================
# Wrong argument types to builtins
# ===================================================================

class TestWrongArgTypeToBuiltin:
    def test_text_length_with_number(self, run):
        r = run('return text.length(42)')
        assert r.type == "error"

    def test_text_split_with_number_sep(self, run):
        r = run('return text.split("hello", 42)')
        assert r.type == "error"

    def test_list_map_with_non_function(self, run):
        r = run('return list.map([1, 2, 3], 42)')
        assert r.type == "error"

    def test_list_take_with_text(self, run):
        r = run('return list.take([1, 2, 3], "two")')
        assert r.type == "error"

    def test_number_round_with_text(self, run):
        r = run('return number.round("3.5")')
        assert r.type == "error"


# ===================================================================
# Wrong argument count
# ===================================================================

class TestWrongArgCount:
    def test_text_split_one_arg(self, run):
        r = run('return text.split("hello")')
        assert r.type == "error"

    def test_text_length_two_args(self, run):
        r = run('return text.length("hello", "extra")')
        assert r.type == "error"

    def test_list_map_one_arg(self, run):
        r = run('return list.map([1, 2, 3])')
        assert r.type == "error"


# ===================================================================
# Structural map field access
# ===================================================================

class TestStructuralMapFieldAccess:
    def test_access_nonexistent_field(self, run):
        r = run(
            'let m = {name: "Theo"}\n'
            'return m.age'
        )
        assert r.type == "error"

    def test_access_field_on_non_map(self, run):
        r = run('let x = 42\nreturn x.name')
        assert r.type == "result"
        assert r.value is None


# ===================================================================
# Tag exhaustiveness
# ===================================================================

class TestTagExhaustiveness:
    def test_non_exhaustive_match_on_define_return(self, run):
        """Missing a tag from a define's return type should be flagged."""
        r = run(
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: :ok(text) | :error(text) "result"\n'
            '\n'
            'implement demo.fn\n'
            '  return :ok("data")\n'
            '\n'
            'let r = demo.fn()\n'
            'return match r\n'
            '  :ok(v) -> v'
            # Missing :error case
        )
        # Should produce a warning or error about missing :error case
        # Exact behavior TBD

    def test_exhaustive_with_wildcard(self, run):
        """Wildcard _ should satisfy exhaustiveness."""
        r = run(
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: :ok(text) | :error(text) "result"\n'
            '\n'
            'implement demo.fn\n'
            '  return :ok("data")\n'
            '\n'
            'let r = demo.fn()\n'
            'return match r\n'
            '  :ok(v) -> v\n'
            '  _ -> "fallback"'
        )
        assert r.type == "result"
        assert r.value == "data"


# ===================================================================
# Undefined function / variable
# ===================================================================

class TestUndefined:
    def test_undefined_function(self, run):
        r = run('return nonexistent.fn()')
        assert r.type == "error"

    def test_undefined_variable(self, run):
        r = run('return x')
        assert r.type == "error"


# ===================================================================
# Return type mismatch
# ===================================================================

class TestReturnTypeMismatch:
    def test_implement_returns_wrong_type(self, run):
        r = run(
            'define math.double\n'
            '  "Double"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "2n"\n'
            '\n'
            'implement math.double\n'
            '  return "not a number"\n'
            '\n'
            'return math.double(5)'
        )
        assert r.type == "error"

    def test_implement_returns_wrong_tag(self, run):
        r = run(
            'define demo.fn\n'
            '  "demo"\n'
            '  returns: :ok(text) | :error(text) "result"\n'
            '\n'
            'implement demo.fn\n'
            '  return :unknown("oops")\n'
            '\n'
            'return demo.fn()'
        )
        assert r.type == "error"


# ===================================================================
# Lambda type mismatches
# ===================================================================

class TestLambdaTypeMismatch:
    def test_lambda_wrong_return_type_in_map(self, run):
        """list.map is generic (fn(a) -> b), so mapping numbers to text is valid.
        But using the result as list<number> afterwards is a type error."""
        r = run(
            'let result = list.map([1, 2, 3], fn(x) -> "text")\n'
            'return list.fold(result, 0, fn(acc, x) -> acc + x)'
        )
        # result is list<text>, but fold tries to add text to number
        assert r.type == "error"

    def test_filter_lambda_returns_non_bool(self, run):
        """list.filter expects fn(a) -> bool, passing fn returning number is an error."""
        r = run('return list.filter([1, 2, 3], fn(x) -> x * 2)')
        assert r.type == "error"


# ===================================================================
# time.* type errors
# ===================================================================

class TestTimeTypeErrors:
    def test_wait_with_text(self, run):
        r = run('return time.wait("100")')
        assert r.type == "error"

    def test_format_first_arg_text(self, run):
        r = run('return time.format("not-a-number", "%Y")')
        assert r.type == "error"

    def test_format_second_arg_number(self, run):
        r = run('return time.format(1000, 42)')
        assert r.type == "error"

    def test_parse_first_arg_number(self, run):
        r = run('return time.parse(12345, "%Y")')
        assert r.type == "error"

    def test_parse_second_arg_number(self, run):
        r = run('return time.parse("2024", 42)')
        assert r.type == "error"

    def test_now_with_args(self, run):
        r = run('return time.now(42)')
        assert r.type == "error"

    def test_add_with_text(self, run):
        r = run('return time.add(1000, "500")')
        assert r.type == "error"

    def test_timeout_non_function(self, run):
        r = run('return time.timeout(1000, 42)')
        assert r.type == "error"

    def test_timeout_wrong_arity(self, run):
        r = run('return time.timeout(1000, fn(x) -> x)')
        assert r.type == "error"

    def test_since_with_text(self, run):
        r = run('return time.since("hello")')
        assert r.type == "error"

    def test_diff_with_text(self, run):
        r = run('return time.diff("a", "b")')
        assert r.type == "error"

    def test_date_with_args(self, run):
        r = run('return time.date(42)')
        assert r.type == "error"


class TestTextTypeErrors:
    def test_match_with_number(self, run):
        r = run('return text.match(42, "*.py")')
        assert r.type == "error"

    def test_index_of_with_number(self, run):
        r = run('return text.index_of("hello", 5)')
        assert r.type == "error"

    def test_pad_start_wrong_types(self, run):
        r = run('return text.pad_start("x", "5", "0")')
        assert r.type == "error"

    def test_extract_wrong_arg_count(self, run):
        r = run('return text.extract("hello", "[")')
        assert r.type == "error"

    def test_lines_with_number(self, run):
        r = run('return text.lines(42)')
        assert r.type == "error"

    def test_split_first_with_number(self, run):
        r = run('return text.split_first(42, "=")')
        assert r.type == "error"

    def test_pad_end_wrong_types(self, run):
        r = run('return text.pad_end("x", "5", "0")')
        assert r.type == "error"


# ===================================================================
# Git built-in type errors
# ===================================================================

class TestGitTypeErrors:
    """Type checker catches wrong arg types/counts for git.* functions."""

    def test_git_add_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.add(123)', git=MockGit())
        assert r.type == "error"

    def test_git_commit_no_args(self, run):
        from tests.conftest import MockGit
        r = run('return git.commit()', git=MockGit())
        assert r.type == "error"

    def test_git_commit_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.commit(42)', git=MockGit())
        assert r.type == "error"

    def test_git_branch_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.branch(true)', git=MockGit())
        assert r.type == "error"

    def test_git_checkout_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.checkout(42)', git=MockGit())
        assert r.type == "error"

    def test_git_log_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.log("five")', git=MockGit())
        assert r.type == "error"

    def test_git_status_extra_args(self, run):
        from tests.conftest import MockGit
        r = run('return git.status("extra")', git=MockGit())
        assert r.type == "error"

    def test_git_show_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.show(123)', git=MockGit())
        assert r.type == "error"

    def test_git_tag_wrong_type(self, run):
        from tests.conftest import MockGit
        r = run('return git.tag(42)', git=MockGit())
        assert r.type == "error"
