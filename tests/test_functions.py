"""Tests for Lumon functions: define/implement, lambdas, closures, recursion."""

import pytest


@pytest.fixture
def run(runner):
    def _run(code, **kwargs):
        return runner.run(code, **kwargs)
    return _run


# ===================================================================
# define / implement
# ===================================================================

class TestDefineImplement:
    def test_basic_define_implement_call(self, run):
        r = run(
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
        assert r.value == 42

    def test_parameters_available_as_bindings(self, run):
        r = run(
            'define greet.hello\n'
            '  "Greet someone"\n'
            '  takes:\n'
            '    name: text "Name"\n'
            '  returns: text "Greeting"\n'
            '\n'
            'implement greet.hello\n'
            '  return "Hello, " + name\n'
            '\n'
            'return greet.hello("World")'
        )
        assert r.value == "Hello, World"

    def test_default_parameter(self, run):
        r = run(
            'define greet.hello\n'
            '  "Greet someone"\n'
            '  takes:\n'
            '    name: text "Name" = "World"\n'
            '  returns: text "Greeting"\n'
            '\n'
            'implement greet.hello\n'
            '  return "Hello, " + name\n'
            '\n'
            'return greet.hello()'
        )
        assert r.value == "Hello, World"

    def test_default_parameter_overridden(self, run):
        r = run(
            'define greet.hello\n'
            '  "Greet someone"\n'
            '  takes:\n'
            '    name: text "Name" = "World"\n'
            '  returns: text "Greeting"\n'
            '\n'
            'implement greet.hello\n'
            '  return "Hello, " + name\n'
            '\n'
            'return greet.hello("Lumon")'
        )
        assert r.value == "Hello, Lumon"

    def test_multiple_parameters(self, run):
        r = run(
            'define math.add\n'
            '  "Add two numbers"\n'
            '  takes:\n'
            '    a: number "First"\n'
            '    b: number "Second"\n'
            '  returns: number "Sum"\n'
            '\n'
            'implement math.add\n'
            '  return a + b\n'
            '\n'
            'return math.add(3, 4)'
        )
        assert r.value == 7

    def test_no_parameters(self, run):
        r = run(
            'define const.pi\n'
            '  "Return pi"\n'
            '  returns: number "Pi"\n'
            '\n'
            'implement const.pi\n'
            '  return 3.14\n'
            '\n'
            'return const.pi()'
        )
        assert r.value == pytest.approx(3.14)

    def test_return_exits_implement_from_match(self, run):
        """return inside a match arm exits the implement block."""
        r = run(
            'define check.sign\n'
            '  "Check sign"\n'
            '  takes:\n'
            '    n: number "Number"\n'
            '  returns: text "Sign"\n'
            '\n'
            'implement check.sign\n'
            '  match n\n'
            '    0 -> return "zero"\n'
            '    x if x > 0 -> return "positive"\n'
            '    _ -> return "negative"\n'
            '\n'
            'return check.sign(-5)'
        )
        assert r.value == "negative"

    def test_return_exits_implement_from_if(self, run):
        """return inside an if branch exits the implement block."""
        r = run(
            'define check.pos\n'
            '  "Check positive"\n'
            '  takes:\n'
            '    n: number "Number"\n'
            '  returns: text "Result"\n'
            '\n'
            'implement check.pos\n'
            '  if n > 0\n'
            '    return "positive"\n'
            '  return "not positive"\n'
            '\n'
            'return check.pos(5)'
        )
        assert r.value == "positive"

    def test_functions_calling_each_other(self, run):
        r = run(
            'define math.double\n'
            '  "Double"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "2n"\n'
            '\n'
            'implement math.double\n'
            '  return n * 2\n'
            '\n'
            'define math.quadruple\n'
            '  "Quadruple"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "4n"\n'
            '\n'
            'implement math.quadruple\n'
            '  return math.double(math.double(n))\n'
            '\n'
            'return math.quadruple(3)'
        )
        assert r.value == 12

    def test_function_returning_tag(self, run):
        r = run(
            'define safe.div\n'
            '  "Safe division"\n'
            '  takes:\n'
            '    a: number "Numerator"\n'
            '    b: number "Denominator"\n'
            '  returns: :ok(number) | :error(text) "Result or error"\n'
            '\n'
            'implement safe.div\n'
            '  if b == 0\n'
            '    return :error("division by zero")\n'
            '  return :ok(a / b)\n'
            '\n'
            'return safe.div(10, 0)'
        )
        assert r.value == {"tag": "error", "value": "division by zero"}


# ===================================================================
# Lambdas
# ===================================================================

class TestLambdas:
    def test_single_expression_lambda(self, run):
        r = run(
            'let double = fn(x) -> x * 2\n'
            'return double(21)'
        )
        assert r.value == 42

    def test_lambda_with_two_params(self, run):
        r = run(
            'let add = fn(a, b) -> a + b\n'
            'return add(3, 4)'
        )
        assert r.value == 7

    def test_lambda_in_list_map(self, run):
        r = run(
            'let result = [1, 2, 3] |> list.map(fn(x) -> x * 2)\n'
            'return result'
        )
        assert r.value == [2, 4, 6]

    def test_lambda_in_list_filter(self, run):
        r = run(
            'let result = [1, 2, 3, 4, 5] |> list.filter(fn(x) -> x > 3)\n'
            'return result'
        )
        assert r.value == [4, 5]

    def test_lambda_in_list_fold(self, run):
        r = run(
            'let result = [1, 2, 3] |> list.fold(0, fn(sum, x) -> sum + x)\n'
            'return result'
        )
        assert r.value == 6

    def test_multi_line_lambda(self, run):
        r = run(
            'let process = fn(x) ->\n'
            '  let doubled = x * 2\n'
            '  doubled + 1\n'
            'return process(5)'
        )
        assert r.value == 11

    def test_lambda_returns_map(self, run):
        r = run(
            'let make = fn(n) -> {value: n, doubled: n * 2}\n'
            'return make(5)'
        )
        assert r.value == {"value": 5, "doubled": 10}


# ===================================================================
# Multi-line lambdas inside function arguments
# ===================================================================

class TestMultiLineLambdaArgs:
    def test_multiline_lambda_in_list_map(self, run):
        """Multi-line lambda with let binding passed to list.map."""
        r = run(
            'let result = list.map([1, 2, 3], fn(x) ->\n'
            '  let doubled = x * 2\n'
            '  doubled + 1\n'
            ')\n'
            'return result'
        )
        assert r.value == [3, 5, 7]

    def test_multiline_lambda_in_list_fold(self, run):
        """Multi-line lambda with let binding passed to list.fold."""
        r = run(
            'let result = list.fold([1, 2, 3], [], fn(acc, x) ->\n'
            '  let doubled = x * 2\n'
            '  list.concat(acc, [doubled])\n'
            ')\n'
            'return result'
        )
        assert r.value == [2, 4, 6]

    def test_nested_multiline_lambdas(self, run):
        """Nested multi-line lambdas inside function call arguments."""
        r = run(
            'let result = list.map([1, 2, 3], fn(x) ->\n'
            '  let inner = list.map([10, 20], fn(y) ->\n'
            '    let sum = x + y\n'
            '    sum\n'
            '  )\n'
            '  list.fold(inner, 0, fn(a, b) -> a + b)\n'
            ')\n'
            'return result'
        )
        assert r.value == [32, 34, 36]

    def test_multiline_lambda_trailing_arg(self, run):
        """Multi-line lambda as trailing argument after other args."""
        r = run(
            'let result = list.fold([1, 2, 3], 0, fn(sum, x) ->\n'
            '  let sq = x * x\n'
            '  sum + sq\n'
            ')\n'
            'return result'
        )
        assert r.value == 14

    def test_inline_lambda_in_function_call_still_works(self, run):
        """Inline lambda inside function call (regression check)."""
        r = run(
            'let result = list.map([1, 2, 3], fn(x) -> x * 2)\n'
            'return result'
        )
        assert r.value == [2, 4, 6]


# ===================================================================
# Closures
# ===================================================================

class TestClosures:
    def test_captures_outer_binding(self, run):
        r = run(
            'let threshold = 18\n'
            'let adults = [15, 20, 17, 25] |> list.filter(fn(age) -> age >= threshold)\n'
            'return adults'
        )
        assert r.value == [20, 25]

    def test_captures_multiple_bindings(self, run):
        r = run(
            'let base = 10\n'
            'let multiplier = 3\n'
            'let result = [1, 2, 3] |> list.map(fn(x) -> base + x * multiplier)\n'
            'return result'
        )
        assert r.value == [13, 16, 19]

    def test_closure_immutable_capture(self, run):
        """Captured bindings are immutable — shadowing outer doesn't affect closure."""
        r = run(
            'let x = 10\n'
            'let f = fn(n) -> n + x\n'
            'let x = 20\n'
            'return f(5)'
        )
        # x was 10 when f was created, shadowing to 20 doesn't change it
        assert r.value == 15


# ===================================================================
# Recursion
# ===================================================================

class TestRecursion:
    def test_recursive_function(self, run):
        r = run(
            'define math.factorial\n'
            '  "Compute factorial"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "n!"\n'
            '\n'
            'implement math.factorial\n'
            '  if n <= 1\n'
            '    return 1\n'
            '  return n * math.factorial(n - 1)\n'
            '\n'
            'return math.factorial(5)'
        )
        assert r.value == 120

    def test_recursion_depth_limit_exceeded(self, run):
        """Infinite recursion hits the interpreter depth limit."""
        r = run(
            'define inf.loop\n'
            '  "Infinite"\n'
            '  takes:\n'
            '    n: number "n"\n'
            '  returns: number "never"\n'
            '\n'
            'implement inf.loop\n'
            '  return inf.loop(n + 1)\n'
            '\n'
            'return inf.loop(0)'
        )
        assert r.type == "error"
