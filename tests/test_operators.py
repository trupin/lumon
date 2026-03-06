"""Tests for Lumon operators: arithmetic, comparison, boolean, nil-coalescing,
pipe, and access operators."""

import pytest


@pytest.fixture
def run(runner):
    def _run(code):
        return runner.run(code)
    return _run


# ===================================================================
# Arithmetic
# ===================================================================

class TestArithmeticAdd:
    def test_add_integers(self, run):
        r = run("return 2 + 3")
        assert r.value == 5

    def test_add_floats(self, run):
        r = run("return 1.5 + 2.5")
        assert r.value == pytest.approx(4.0)

    def test_add_int_and_float(self, run):
        r = run("return 1 + 0.5")
        assert r.value == pytest.approx(1.5)

    def test_concat_text(self, run):
        r = run('return "hello" + " world"')
        assert r.value == "hello world"

    def test_concat_empty_text(self, run):
        r = run('return "" + "hello"')
        assert r.value == "hello"

    def test_concat_after_match(self, run):
        """String concatenation with + after match returns TAny, chained concat should work."""
        code = '''\
let x = :ok("hello")
let a = match x
  :ok(v) -> v
  _ -> "default"
let b = a + "y"
return b + "z"'''
        r = run(code)
        assert r.value == "helloyz"


class TestArithmeticSubtract:
    def test_subtract(self, run):
        r = run("return 10 - 3")
        assert r.value == 7

    def test_subtract_negative_result(self, run):
        r = run("return 3 - 10")
        assert r.value == -7


class TestArithmeticMultiply:
    def test_multiply(self, run):
        r = run("return 4 * 5")
        assert r.value == 20

    def test_multiply_by_zero(self, run):
        r = run("return 42 * 0")
        assert r.value == 0


class TestArithmeticDivide:
    def test_divide(self, run):
        r = run("return 10 / 2")
        assert r.value == pytest.approx(5.0)

    def test_divide_float_result(self, run):
        r = run("return 7 / 2")
        assert r.value == pytest.approx(3.5)

    def test_division_by_zero_is_interpreter_error(self, run):
        r = run("return 1 / 0")
        assert r.type == "error"
        assert "division" in r.error["message"].lower() or "zero" in r.error["message"].lower()


class TestArithmeticModulo:
    def test_modulo(self, run):
        r = run("return 10 % 3")
        assert r.value == 1

    def test_modulo_even(self, run):
        r = run("return 10 % 2")
        assert r.value == 0


# ===================================================================
# Comparison
# ===================================================================

class TestComparison:
    def test_equal_numbers(self, run):
        r = run("return 1 == 1")
        assert r.value is True

    def test_not_equal_numbers(self, run):
        r = run("return 1 != 2")
        assert r.value is True

    def test_equal_text(self, run):
        r = run('return "a" == "a"')
        assert r.value is True

    def test_not_equal_text(self, run):
        r = run('return "a" != "b"')
        assert r.value is True

    def test_less_than(self, run):
        r = run("return 1 < 2")
        assert r.value is True

    def test_less_than_false(self, run):
        r = run("return 2 < 1")
        assert r.value is False

    def test_greater_than(self, run):
        r = run("return 2 > 1")
        assert r.value is True

    def test_less_equal(self, run):
        r = run("return 2 <= 2")
        assert r.value is True

    def test_greater_equal(self, run):
        r = run("return 2 >= 3")
        assert r.value is False

    def test_equal_bools(self, run):
        r = run("return true == true")
        assert r.value is True

    def test_none_equals_none(self, run):
        r = run("return none == none")
        assert r.value is True

    def test_none_not_equal_to_value(self, run):
        r = run("return none != 0")
        assert r.value is True

    def test_tag_equality_same(self, run):
        r = run("return :ok == :ok")
        assert r.value is True

    def test_tag_equality_different(self, run):
        r = run("return :ok != :error")
        assert r.value is True

    def test_tag_equality_with_payload(self, run):
        r = run('return :error("a") == :error("a")')
        assert r.value is True

    def test_tag_inequality_different_payload(self, run):
        r = run('return :error("a") != :error("b")')
        assert r.value is True


# ===================================================================
# Boolean
# ===================================================================

class TestBooleanOperators:
    def test_and_true_true(self, run):
        r = run("return true and true")
        assert r.value is True

    def test_and_true_false(self, run):
        r = run("return true and false")
        assert r.value is False

    def test_and_false_short_circuits(self, run):
        """false and <anything> should return false without evaluating RHS."""
        r = run("return false and true")
        assert r.value is False

    def test_or_false_true(self, run):
        r = run("return false or true")
        assert r.value is True

    def test_or_true_short_circuits(self, run):
        r = run("return true or false")
        assert r.value is True

    def test_or_false_false(self, run):
        r = run("return false or false")
        assert r.value is False

    def test_not_true(self, run):
        r = run("return not true")
        assert r.value is False

    def test_not_false(self, run):
        r = run("return not false")
        assert r.value is True

    def test_not_truthy_value(self, run):
        r = run("return not 1")
        assert r.value is False

    def test_not_falsy_value(self, run):
        r = run("return not 0")
        assert r.value is True


# ===================================================================
# Nil-coalescing (??)
# ===================================================================

class TestNilCoalescing:
    def test_none_returns_default(self, run):
        r = run('return none ?? "default"')
        assert r.value == "default"

    def test_value_returns_value(self, run):
        r = run('return "value" ?? "default"')
        assert r.value == "value"

    def test_zero_is_not_none(self, run):
        """0 is falsy but not none — ?? should return 0."""
        r = run("return 0 ?? 1")
        assert r.value == 0

    def test_empty_string_is_not_none(self, run):
        r = run('return "" ?? "default"')
        assert r.value == ""

    def test_false_is_not_none(self, run):
        r = run("return false ?? true")
        assert r.value is False

    def test_chained_coalescing(self, run):
        r = run('return none ?? none ?? "found"')
        assert r.value == "found"


# ===================================================================
# Pipe operator (|>)
# ===================================================================

class TestPipeOperator:
    def test_pipe_to_single_arg_function(self, run):
        r = run("[3, 1, 2] |> list.sort |> return")
        # Alternative: may need different syntax
        r = run("let result = [3, 1, 2] |> list.sort\nreturn result")
        assert r.value == [1, 2, 3]

    def test_pipe_with_extra_args(self, run):
        r = run("let result = [1, 2, 3, 4, 5] |> list.take(3)\nreturn result")
        assert r.value == [1, 2, 3]

    def test_chained_pipes(self, run):
        r = run(
            "let result = [5, 3, 8, 1, 9, 2, 7]\n"
            "  |> list.sort\n"
            "  |> list.reverse\n"
            "  |> list.take(3)\n"
            "return result"
        )
        assert r.value == [9, 8, 7]

    def test_pipe_to_lambda(self, run):
        """Pipe to lambda for non-first-argument position."""
        r = run(
            'let replaced = "world" |> fn(t) -> text.replace("hello {}", "{}", t)\n'
            "return replaced"
        )
        assert r.value == "hello world"

    def test_pipe_with_list_map(self, run):
        r = run(
            "let result = [1, 2, 3]\n"
            "  |> list.map(fn(x) -> x * 2)\n"
            "return result"
        )
        assert r.value == [2, 4, 6]


# ===================================================================
# Access operators
# ===================================================================

class TestAccessOperators:
    def test_map_field_access(self, run):
        r = run('let m = {name: "Theo"}\nreturn m.name')
        assert r.value == "Theo"

    def test_list_index_access(self, run):
        r = run("let items = [10, 20, 30]\nreturn items[0]")
        assert r.value == 10

    def test_list_index_second(self, run):
        r = run("let items = [10, 20, 30]\nreturn items[1]")
        assert r.value == 20

    def test_list_index_last(self, run):
        r = run("let items = [10, 20, 30]\nreturn items[2]")
        assert r.value == 30

    def test_nested_map_access(self, run):
        r = run('let m = {a: {b: "deep"}}\nreturn m.a.b')
        assert r.value == "deep"

    def test_map_in_list_access(self, run):
        r = run('let items = [{name: "a"}, {name: "b"}]\nreturn items[1].name')
        assert r.value == "b"

    def test_map_keyword_dot_access(self, run):
        """Dot access with a keyword field name like .match (issue #15)."""
        r = run(
            'let m = map.set({}, "match", 99)\n'
            'return m.match'
        )
        assert r.value == 99

    def test_map_keyword_dot_access_true(self, run):
        """Dot access with keyword .true (issue #15)."""
        r = run(
            'let m = map.set({}, "true", "yes")\n'
            'return m.true'
        )
        assert r.value == "yes"

    def test_map_chained_keyword_dot_access(self, run):
        """Chained dot access with keyword field names (issue #15)."""
        r = run(
            'let inner = map.set({}, "none", 7)\n'
            'let outer = map.set({}, "match", inner)\n'
            'return outer.match.none'
        )
        assert r.value == 7


# ===================================================================
# Deep equality for tags, dicts, lists, none
# ===================================================================


class TestDeepEquality:
    def test_tag_equality(self, run):
        r = run("return :ok == :ok")
        assert r.value is True

    def test_tag_inequality(self, run):
        r = run("return :ok == :error")
        assert r.value is False

    def test_tag_payload_equality(self, run):
        r = run('return :ok("a") == :ok("a")')
        assert r.value is True

    def test_tag_payload_inequality(self, run):
        r = run('return :ok("a") == :ok("b")')
        assert r.value is False

    def test_dict_equality(self, run):
        r = run("return {a: 1, b: 2} == {a: 1, b: 2}")
        assert r.value is True

    def test_dict_inequality_values(self, run):
        r = run("return {a: 1} == {a: 2}")
        assert r.value is False

    def test_dict_inequality_keys(self, run):
        r = run("return {a: 1} == {b: 1}")
        assert r.value is False

    def test_list_equality(self, run):
        r = run("return [1, 2, 3] == [1, 2, 3]")
        assert r.value is True

    def test_list_inequality_length(self, run):
        r = run("return [1, 2] == [1, 2, 3]")
        assert r.value is False

    def test_none_equality(self, run):
        r = run("return none == none")
        assert r.value is True

    def test_none_inequality(self, run):
        r = run("return none == 1")
        assert r.value is False

    def test_value_vs_none(self, run):
        r = run("return 1 == none")
        assert r.value is False


# ===================================================================
# Pipe to lambda stored in variable
# ===================================================================


class TestPipeToVariable:
    def test_pipe_to_lambda_var(self, run):
        r = run("let double = fn(x) -> x * 2\nreturn 5 |> double")
        assert r.value == 10

    def test_pipe_to_lambda_inline(self, run):
        r = run("return 5 |> fn(x) -> x + 1")
        assert r.value == 6


# ===================================================================
# Operator error paths
# ===================================================================


class TestOperatorErrors:
    def test_add_incompatible_types(self, run):
        r = run('return 1 + "hello"')
        assert r.type == "error"
