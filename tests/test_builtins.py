"""Tests for Lumon built-in primitives: text.*, list.*, map.*, number.*, type.*"""

import pytest


@pytest.fixture
def run(runner):
    def _run(code):
        return runner.run(code)
    return _run


# ===================================================================
# text.*
# ===================================================================

class TestTextSplit:
    def test_split_by_comma(self, run):
        r = run('return text.split("a,b,c", ",")')
        assert r.value == ["a", "b", "c"]

    def test_split_by_newline(self, run):
        r = run('return text.split("line1\\nline2", "\\n")')
        assert r.value == ["line1", "line2"]

    def test_split_no_match(self, run):
        r = run('return text.split("hello", ",")')
        assert r.value == ["hello"]

    def test_split_empty_string(self, run):
        r = run('return text.split("", ",")')
        assert r.value == [""]


class TestTextJoin:
    def test_join_with_separator(self, run):
        r = run('return text.join(["a", "b", "c"], "-")')
        assert r.value == "a-b-c"

    def test_join_empty_list(self, run):
        r = run('return text.join([], ",")')
        assert r.value == ""

    def test_join_single_element(self, run):
        r = run('return text.join(["only"], ",")')
        assert r.value == "only"

    def test_join_with_empty_separator(self, run):
        r = run('return text.join(["a", "b"], "")')
        assert r.value == "ab"


class TestTextContains:
    def test_contains_true(self, run):
        r = run('return text.contains("hello world", "world")')
        assert r.value is True

    def test_contains_false(self, run):
        r = run('return text.contains("hello world", "xyz")')
        assert r.value is False

    def test_contains_empty_substring(self, run):
        r = run('return text.contains("hello", "")')
        assert r.value is True


class TestTextReplace:
    def test_replace_occurrence(self, run):
        r = run('return text.replace("hello world", "world", "lumon")')
        assert r.value == "hello lumon"

    def test_replace_multiple(self, run):
        r = run('return text.replace("aaa", "a", "b")')
        assert r.value == "bbb"

    def test_replace_no_match(self, run):
        r = run('return text.replace("hello", "xyz", "abc")')
        assert r.value == "hello"


class TestTextSlice:
    def test_slice_middle(self, run):
        r = run('return text.slice("hello", 1, 3)')
        assert r.value == "el"

    def test_slice_from_start(self, run):
        r = run('return text.slice("hello", 0, 2)')
        assert r.value == "he"

    def test_slice_to_end(self, run):
        r = run('return text.slice("hello", 3, 5)')
        assert r.value == "lo"

    def test_slice_full(self, run):
        r = run('return text.slice("hello", 0, 5)')
        assert r.value == "hello"

    def test_slice_clamped_out_of_bounds(self, run):
        """Out-of-bounds indices are clamped."""
        r = run('return text.slice("hello", 0, 100)')
        assert r.value == "hello"

    def test_slice_negative_start_clamped(self, run):
        r = run('return text.slice("hello", -5, 3)')
        assert r.value == "hel"


class TestTextLength:
    def test_length(self, run):
        r = run('return text.length("hello")')
        assert r.value == 5

    def test_length_empty(self, run):
        r = run('return text.length("")')
        assert r.value == 0


class TestTextUpper:
    def test_upper(self, run):
        r = run('return text.upper("hello")')
        assert r.value == "HELLO"


class TestTextLower:
    def test_lower(self, run):
        r = run('return text.lower("HELLO")')
        assert r.value == "hello"


class TestTextTrim:
    def test_trim(self, run):
        r = run('return text.trim("  hello  ")')
        assert r.value == "hello"

    def test_trim_newlines(self, run):
        r = run('return text.trim("\\nhello\\n")')
        assert r.value == "hello"


class TestTextStartsWith:
    def test_starts_with_true(self, run):
        r = run('return text.starts_with("hello", "hel")')
        assert r.value is True

    def test_starts_with_false(self, run):
        r = run('return text.starts_with("hello", "xyz")')
        assert r.value is False


class TestTextEndsWith:
    def test_ends_with_true(self, run):
        r = run('return text.ends_with("hello", "llo")')
        assert r.value is True

    def test_ends_with_false(self, run):
        r = run('return text.ends_with("hello", "xyz")')
        assert r.value is False


class TestTextFrom:
    def test_from_number(self, run):
        r = run('return text.from(42)')
        assert r.value == "42"

    def test_from_float(self, run):
        r = run('return text.from(3.14)')
        assert "3.14" in r.value

    def test_from_bool_true(self, run):
        r = run('return text.from(true)')
        assert r.value == "true"

    def test_from_bool_false(self, run):
        r = run('return text.from(false)')
        assert r.value == "false"

    def test_from_none(self, run):
        r = run('return text.from(none)')
        assert r.value == "none"

    def test_from_list(self, run):
        r = run('return text.from([1, 2, 3])')
        assert isinstance(r.value, str)

    def test_from_whole_float(self, run):
        """text.from should not produce trailing .0 for whole-number floats."""
        r = run('return text.from((4500 + 5050) / 2)')
        assert r.value == "4775"

    def test_from_real_float(self, run):
        """text.from should preserve decimals for non-whole floats."""
        r = run('return text.from(3.14)')
        assert r.value == "3.14"


class TestTextMatch:
    def test_wildcard(self, run):
        r = run('return text.match("hello.py", "*.py")')
        assert r.value is True

    def test_question_mark(self, run):
        r = run('return text.match("cat", "c?t")')
        assert r.value is True

    def test_brackets(self, run):
        r = run('return text.match("cat", "[abc]at")')
        assert r.value is True

    def test_negated_brackets(self, run):
        r = run('return text.match("cat", "[!d]at")')
        assert r.value is True

    def test_exact_match(self, run):
        r = run('return text.match("hello", "hello")')
        assert r.value is True

    def test_no_match(self, run):
        r = run('return text.match("hello.py", "*.js")')
        assert r.value is False

    def test_empty_string(self, run):
        r = run('return text.match("", "*")')
        assert r.value is True

    def test_empty_pattern_no_match(self, run):
        r = run('return text.match("hello", "")')
        assert r.value is False


class TestTextIndexOf:
    def test_found(self, run):
        r = run('return text.index_of("hello world", "world")')
        assert r.value == 6

    def test_not_found(self, run):
        r = run('return text.index_of("hello", "xyz")')
        assert r.value is None

    def test_at_start(self, run):
        r = run('return text.index_of("hello", "hel")')
        assert r.value == 0

    def test_empty_substring(self, run):
        r = run('return text.index_of("hello", "")')
        assert r.value == 0

    def test_empty_string(self, run):
        r = run('return text.index_of("", "a")')
        assert r.value is None


class TestTextLines:
    def test_basic(self, run):
        r = run('return text.lines("a\nb\nc")')
        assert r.value == ["a", "b", "c"]

    def test_single_line(self, run):
        r = run('return text.lines("hello")')
        assert r.value == ["hello"]

    def test_empty(self, run):
        r = run('return text.lines("")')
        assert r.value == [""]

    def test_trailing_newline(self, run):
        r = run('return text.lines("a\nb\n")')
        assert r.value == ["a", "b", ""]


class TestTextSplitFirst:
    def test_found(self, run):
        r = run('return text.split_first("key=value", "=")')
        assert r.value == {"before": "key", "after": "value"}

    def test_not_found(self, run):
        r = run('return text.split_first("hello", "=")')
        assert r.value == {"before": "hello", "after": ""}

    def test_multiple_seps(self, run):
        r = run('return text.split_first("a=b=c", "=")')
        assert r.value == {"before": "a", "after": "b=c"}

    def test_at_start(self, run):
        r = run('return text.split_first("=value", "=")')
        assert r.value == {"before": "", "after": "value"}


class TestTextExtract:
    def test_code_blocks(self, run):
        r = run('return text.extract("before ```code``` after", "```", "```")')
        assert r.value == ["code"]

    def test_multiple(self, run):
        r = run('return text.extract("[a] and [b]", "[", "]")')
        assert r.value == ["a", "b"]

    def test_none_found(self, run):
        r = run('return text.extract("no delimiters", "[", "]")')
        assert r.value == []

    def test_unclosed(self, run):
        r = run('return text.extract("[open but no close", "[", "]")')
        assert r.value == []

    def test_empty_content(self, run):
        r = run('return text.extract("[]", "[", "]")')
        assert r.value == [""]

    def test_empty_start_delimiter_error(self, run):
        r = run('return text.extract("abc", "", "]")')
        assert r.type == "error"

    def test_empty_end_delimiter_error(self, run):
        r = run('return text.extract("abc", "[", "")')
        assert r.type == "error"


class TestTextPadStart:
    def test_basic(self, run):
        r = run('return text.pad_start("5", 3, "0")')
        assert r.value == "005"

    def test_already_long(self, run):
        r = run('return text.pad_start("hello", 3, "0")')
        assert r.value == "hello"

    def test_multi_char_fill(self, run):
        r = run('return text.pad_start("x", 5, "ab")')
        assert r.value == "ababx"

    def test_empty_fill_error(self, run):
        r = run('return text.pad_start("x", 5, "")')
        assert r.type == "error"


class TestTextPadEnd:
    def test_basic(self, run):
        r = run('return text.pad_end("5", 3, "0")')
        assert r.value == "500"

    def test_already_long(self, run):
        r = run('return text.pad_end("hello", 3, "0")')
        assert r.value == "hello"

    def test_multi_char_fill(self, run):
        r = run('return text.pad_end("x", 5, "ab")')
        assert r.value == "xabab"

    def test_empty_fill_error(self, run):
        r = run('return text.pad_end("x", 5, "")')
        assert r.type == "error"


# ===================================================================
# list.*
# ===================================================================

class TestListMap:
    def test_map_double(self, run):
        r = run('return list.map([1, 2, 3], fn(x) -> x * 2)')
        assert r.value == [2, 4, 6]

    def test_map_empty(self, run):
        r = run('return list.map([], fn(x) -> x * 2)')
        assert r.value == []

    def test_map_to_strings(self, run):
        r = run('return list.map([1, 2, 3], fn(x) -> text.from(x))')
        assert r.value == ["1", "2", "3"]


class TestListFilter:
    def test_filter_gt(self, run):
        r = run('return list.filter([1, 2, 3, 4, 5], fn(x) -> x > 3)')
        assert r.value == [4, 5]

    def test_filter_none_match(self, run):
        r = run('return list.filter([1, 2, 3], fn(x) -> x > 10)')
        assert r.value == []

    def test_filter_all_match(self, run):
        r = run('return list.filter([1, 2, 3], fn(x) -> x > 0)')
        assert r.value == [1, 2, 3]


class TestListFold:
    def test_fold_sum(self, run):
        r = run('return list.fold([1, 2, 3], 0, fn(acc, x) -> acc + x)')
        assert r.value == 6

    def test_fold_product(self, run):
        r = run('return list.fold([1, 2, 3, 4], 1, fn(acc, x) -> acc * x)')
        assert r.value == 24

    def test_fold_empty(self, run):
        r = run('return list.fold([], 0, fn(acc, x) -> acc + x)')
        assert r.value == 0


class TestListFlatMap:
    def test_flat_map(self, run):
        r = run('return list.flat_map([1, 2, 3], fn(x) -> [x, x * 10])')
        assert r.value == [1, 10, 2, 20, 3, 30]

    def test_flat_map_empty_results(self, run):
        r = run('return list.flat_map([1, 2, 3], fn(x) -> [])')
        assert r.value == []


class TestListSort:
    def test_sort_numbers(self, run):
        r = run('return list.sort([3, 1, 2])')
        assert r.value == [1, 2, 3]

    def test_sort_strings(self, run):
        r = run('return list.sort(["c", "a", "b"])')
        assert r.value == ["a", "b", "c"]

    def test_sort_empty(self, run):
        r = run('return list.sort([])')
        assert r.value == []

    def test_sort_already_sorted(self, run):
        r = run('return list.sort([1, 2, 3])')
        assert r.value == [1, 2, 3]


class TestListSortBy:
    def test_sort_by_key(self, run):
        r = run(
            'let items = [{name: "b", val: 2}, {name: "a", val: 1}]\n'
            'return list.sort_by(items, fn(x) -> x.val)'
        )
        assert r.value == [{"name": "a", "val": 1}, {"name": "b", "val": 2}]


class TestListTake:
    def test_take(self, run):
        r = run('return list.take([1, 2, 3, 4, 5], 3)')
        assert r.value == [1, 2, 3]

    def test_take_more_than_length(self, run):
        r = run('return list.take([1, 2], 5)')
        assert r.value == [1, 2]

    def test_take_zero(self, run):
        r = run('return list.take([1, 2, 3], 0)')
        assert r.value == []


class TestListDrop:
    def test_drop(self, run):
        r = run('return list.drop([1, 2, 3, 4, 5], 2)')
        assert r.value == [3, 4, 5]

    def test_drop_all(self, run):
        r = run('return list.drop([1, 2, 3], 5)')
        assert r.value == []


class TestListDeduplicate:
    def test_deduplicate(self, run):
        r = run('return list.deduplicate([1, 1, 2, 3, 2])')
        assert r.value == [1, 2, 3]

    def test_deduplicate_preserves_order(self, run):
        r = run('return list.deduplicate([3, 1, 2, 1, 3])')
        assert r.value == [3, 1, 2]


class TestListLength:
    def test_length(self, run):
        r = run('return list.length([1, 2, 3])')
        assert r.value == 3

    def test_length_empty(self, run):
        r = run('return list.length([])')
        assert r.value == 0


class TestListContains:
    def test_contains_true(self, run):
        r = run('return list.contains([1, 2, 3], 2)')
        assert r.value is True

    def test_contains_false(self, run):
        r = run('return list.contains([1, 2, 3], 4)')
        assert r.value is False


class TestListReverse:
    def test_reverse(self, run):
        r = run('return list.reverse([1, 2, 3])')
        assert r.value == [3, 2, 1]

    def test_reverse_empty(self, run):
        r = run('return list.reverse([])')
        assert r.value == []


class TestListFlatten:
    def test_flatten(self, run):
        r = run('return list.flatten([[1, 2], [3, 4]])')
        assert r.value == [1, 2, 3, 4]

    def test_flatten_mixed_lengths(self, run):
        r = run('return list.flatten([[1], [2, 3], [4]])')
        assert r.value == [1, 2, 3, 4]

    def test_flatten_empty(self, run):
        r = run('return list.flatten([])')
        assert r.value == []


class TestListHead:
    def test_head_nonempty(self, run):
        r = run('return list.head([10, 20, 30])')
        assert r.value == 10

    def test_head_empty(self, run):
        r = run('return list.head([])')
        assert r.value is None

    def test_head_single(self, run):
        r = run('return list.head([42])')
        assert r.value == 42


class TestListTail:
    def test_tail(self, run):
        r = run('return list.tail([1, 2, 3])')
        assert r.value == [2, 3]

    def test_tail_single(self, run):
        r = run('return list.tail([1])')
        assert r.value == []

    def test_tail_empty(self, run):
        r = run('return list.tail([])')
        assert r.value == []


class TestListConcat:
    def test_concat(self, run):
        r = run('return list.concat([1, 2], [3, 4])')
        assert r.value == [1, 2, 3, 4]

    def test_concat_with_empty(self, run):
        r = run('return list.concat([], [1, 2])')
        assert r.value == [1, 2]

    def test_concat_both_empty(self, run):
        r = run('return list.concat([], [])')
        assert r.value == []


# ===================================================================
# map.*
# ===================================================================

class TestMapGet:
    def test_get_existing(self, run):
        r = run(
            'let m = map.set({}, "a", 1)\n'
            'return map.get(m, "a")'
        )
        assert r.value == 1

    def test_get_missing(self, run):
        r = run('return map.get({}, "x")')
        assert r.value is None

    def test_get_from_literal(self, run):
        """map.get on uniform map built with map.set."""
        r = run(
            'let m = map.set(map.set({}, "a", 1), "b", 2)\n'
            'return map.get(m, "b")'
        )
        assert r.value == 2


class TestMapSet:
    def test_set_new_key(self, run):
        r = run('return map.set({}, "k", "v")')
        assert r.value == {"k": "v"}

    def test_set_overwrites(self, run):
        r = run(
            'let m = map.set({}, "k", "old")\n'
            'return map.set(m, "k", "new")'
        )
        assert r.value == {"k": "new"}


class TestMapKeys:
    def test_keys(self, run):
        r = run(
            'let m = map.set(map.set({}, "a", 1), "b", 2)\n'
            'return map.keys(m) |> list.sort'
        )
        assert r.value == ["a", "b"]

    def test_keys_empty(self, run):
        r = run('return map.keys({})')
        assert r.value == []


class TestMapValues:
    def test_values(self, run):
        r = run(
            'let m = map.set(map.set({}, "a", 1), "b", 2)\n'
            'return map.values(m) |> list.sort'
        )
        assert r.value == [1, 2]


class TestMapMerge:
    def test_merge(self, run):
        r = run(
            'let m1 = map.set({}, "a", 1)\n'
            'let m2 = map.set({}, "b", 2)\n'
            'return map.merge(m1, m2)'
        )
        assert r.value == {"a": 1, "b": 2}

    def test_merge_overwrites(self, run):
        r = run(
            'let m1 = map.set({}, "a", 1)\n'
            'let m2 = map.set({}, "a", 99)\n'
            'return map.merge(m1, m2)'
        )
        assert r.value == {"a": 99}


class TestMapHas:
    def test_has_true(self, run):
        r = run(
            'let m = map.set({}, "key", "val")\n'
            'return map.has(m, "key")'
        )
        assert r.value is True

    def test_has_false(self, run):
        r = run('return map.has({}, "key")')
        assert r.value is False


class TestMapRemove:
    def test_remove(self, run):
        r = run(
            'let m = map.set(map.set({}, "a", 1), "b", 2)\n'
            'return map.remove(m, "a")'
        )
        assert r.value == {"b": 2}

    def test_remove_nonexistent(self, run):
        r = run(
            'let m = map.set({}, "a", 1)\n'
            'return map.remove(m, "z")'
        )
        assert r.value == {"a": 1}


class TestMapEntries:
    def test_entries(self, run):
        r = run(
            'let m = map.set(map.set({}, "a", 1), "b", 2)\n'
            'let entries = map.entries(m) |> list.sort_by(fn(e) -> e.key)\n'
            'return entries'
        )
        assert r.value == [
            {"key": "a", "value": 1},
            {"key": "b", "value": 2},
        ]


# ===================================================================
# number.*
# ===================================================================

class TestNumberRound:
    def test_round(self, run):
        r = run('return number.round(3.7)')
        assert r.value == 4

    def test_round_down(self, run):
        r = run('return number.round(3.2)')
        assert r.value == 3


class TestNumberFloor:
    def test_floor(self, run):
        r = run('return number.floor(3.7)')
        assert r.value == 3


class TestNumberCeil:
    def test_ceil(self, run):
        r = run('return number.ceil(3.2)')
        assert r.value == 4


class TestNumberAbs:
    def test_abs_negative(self, run):
        r = run('return number.abs(-5)')
        assert r.value == 5

    def test_abs_positive(self, run):
        r = run('return number.abs(5)')
        assert r.value == 5


class TestNumberMinMax:
    def test_min(self, run):
        r = run('return number.min(3, 7)')
        assert r.value == 3

    def test_max(self, run):
        r = run('return number.max(3, 7)')
        assert r.value == 7


class TestNumberParse:
    def test_parse_integer(self, run):
        r = run('return number.parse("42")')
        assert r.value == 42

    def test_parse_float(self, run):
        r = run('return number.parse("3.14")')
        assert r.value == pytest.approx(3.14)

    def test_parse_invalid(self, run):
        r = run('return number.parse("nope")')
        assert r.value is None

    def test_parse_empty(self, run):
        r = run('return number.parse("")')
        assert r.value is None


class TestNumberRandom:
    def test_random_in_range(self, run):
        r = run('return number.random()')
        assert 0 <= r.value < 1

    def test_random_is_float(self, run):
        r = run('return number.random()')
        assert isinstance(r.value, float)


class TestNumberRandomInt:
    def test_random_int_in_range(self, run):
        r = run('return number.random_int(1, 10)')
        assert 1 <= r.value <= 10
        assert isinstance(r.value, int)

    def test_random_int_min_equals_max(self, run):
        r = run('return number.random_int(5, 5)')
        assert r.value == 5


class TestNumberMod:
    def test_mod_basic(self, run):
        r = run('return number.mod(5, 2)')
        assert r.value == 1

    def test_mod_even(self, run):
        r = run('return number.mod(4, 2)')
        assert r.value == 0

    def test_mod_float(self, run):
        r = run('return number.mod(5.5, 2)')
        assert r.value == pytest.approx(1.5)


class TestNumberPow:
    def test_pow_integer(self, run):
        r = run('return number.pow(2, 10)')
        assert r.value == 1024.0

    def test_pow_fractional(self, run):
        r = run('return number.pow(4, 0.5)')
        assert r.value == pytest.approx(2.0)

    def test_pow_zero_exponent(self, run):
        r = run('return number.pow(5, 0)')
        assert r.value == 1.0


class TestNumberSqrt:
    def test_sqrt_perfect(self, run):
        r = run('return number.sqrt(9)')
        assert r.value == pytest.approx(3.0)

    def test_sqrt_irrational(self, run):
        r = run('return number.sqrt(2)')
        assert r.value == pytest.approx(1.41421356, rel=1e-5)

    def test_sqrt_negative_errors(self, run):
        r = run('return number.sqrt(-1)')
        assert r.error is not None
        assert "sqrt" in r.error["message"]


class TestNumberLog:
    def test_log_one(self, run):
        r = run('return number.log(1)')
        assert r.value == pytest.approx(0.0)

    def test_log_e(self, run):
        r = run('return number.log(number.e())')
        assert r.value == pytest.approx(1.0)

    def test_log_zero_errors(self, run):
        r = run('return number.log(0)')
        assert r.error is not None
        assert "log" in r.error["message"]

    def test_log_negative_errors(self, run):
        r = run('return number.log(-1)')
        assert r.error is not None
        assert "log" in r.error["message"]


class TestNumberSign:
    def test_sign_positive(self, run):
        r = run('return number.sign(42)')
        assert r.value == 1

    def test_sign_negative(self, run):
        r = run('return number.sign(-7)')
        assert r.value == -1

    def test_sign_zero(self, run):
        r = run('return number.sign(0)')
        assert r.value == 0

    def test_sign_float(self, run):
        r = run('return number.sign(-0.5)')
        assert r.value == -1


class TestNumberTruncate:
    def test_truncate_positive(self, run):
        r = run('return number.truncate(3.9)')
        assert r.value == 3

    def test_truncate_negative(self, run):
        r = run('return number.truncate(-3.9)')
        assert r.value == -3


class TestNumberClamp:
    def test_clamp_below(self, run):
        r = run('return number.clamp(1, 5, 10)')
        assert r.value == 5

    def test_clamp_within(self, run):
        r = run('return number.clamp(7, 5, 10)')
        assert r.value == 7

    def test_clamp_above(self, run):
        r = run('return number.clamp(15, 5, 10)')
        assert r.value == 10


class TestNumberToText:
    def test_to_text_integer(self, run):
        r = run('return number.to_text(5)')
        assert r.value == "5"

    def test_to_text_float_no_trailing_zero(self, run):
        r = run('return number.to_text(5.0)')
        assert r.value == "5"

    def test_to_text_float(self, run):
        r = run('return number.to_text(3.14)')
        assert r.value == "3.14"

    def test_to_text_negative(self, run):
        r = run('return number.to_text(-5.0)')
        assert r.value == "-5"

    def test_to_text_negative_float(self, run):
        r = run('return number.to_text(-3.14)')
        assert r.value == "-3.14"

    def test_to_text_infinity(self, run):
        r = run('return number.to_text(number.inf())')
        assert r.value == "inf"


class TestNumberFormat:
    def test_format_zero_decimals(self, run):
        r = run('return number.format(7.0, 0)')
        assert r.value == "7"

    def test_format_one_decimal(self, run):
        r = run('return number.format(7, 1)')
        assert r.value == "7.0"

    def test_format_two_decimals(self, run):
        r = run('return number.format(3.14159, 2)')
        assert r.value == "3.14"

    def test_format_uniform_output(self, run):
        r = run('let a = 3 + 4\nlet b = 3.0 + 4\nreturn [number.format(a, 1), number.format(b, 1)]')
        assert r.value == ["7.0", "7.0"]


class TestNumberPi:
    def test_pi(self, run):
        r = run('return number.pi()')
        assert r.value == pytest.approx(3.14159265, rel=1e-5)


class TestNumberE:
    def test_e(self, run):
        r = run('return number.e()')
        assert r.value == pytest.approx(2.71828182, rel=1e-5)


class TestNumberInf:
    def test_inf(self, run):
        import math
        r = run('return number.inf()')
        assert math.isinf(r.value)
        assert r.value > 0


# ===================================================================
# type.*
# ===================================================================

class TestTypeOf:
    def test_type_of_number(self, run):
        r = run('return type.of(42)')
        assert r.value == "number"

    def test_type_of_text(self, run):
        r = run('return type.of("hello")')
        assert r.value == "text"

    def test_type_of_bool(self, run):
        r = run('return type.of(true)')
        assert r.value == "bool"

    def test_type_of_none(self, run):
        r = run('return type.of(none)')
        assert r.value == "none"

    def test_type_of_list(self, run):
        r = run('return type.of([1, 2, 3])')
        assert r.value == "list"

    def test_type_of_map(self, run):
        r = run('return type.of({a: 1})')
        assert r.value == "map"

    def test_type_of_tag(self, run):
        r = run('return type.of(:ok)')
        assert r.value == "tag"


class TestTypeIs:
    def test_is_number(self, run):
        r = run('return type.is(42, "number")')
        assert r.value is True

    def test_is_text(self, run):
        r = run('return type.is("hi", "text")')
        assert r.value is True

    def test_is_wrong_type(self, run):
        r = run('return type.is(42, "text")')
        assert r.value is False


# ===================================================================
# list.find / list.any / list.all / list.zip / list.enumerate /
# list.group_by / list.index_of / list.unique_by
# ===================================================================

class TestListFind:
    def test_find_match(self, run):
        r = run('return list.find([1, 2, 3, 4], fn(x) -> x > 2)')
        assert r.value == 3

    def test_find_no_match(self, run):
        r = run('return list.find([1, 2, 3], fn(x) -> x > 10)')
        assert r.value is None

    def test_find_empty(self, run):
        r = run('return list.find([], fn(x) -> x > 0)')
        assert r.value is None

    def test_find_first_only(self, run):
        r = run('return list.find([10, 20, 30], fn(x) -> x >= 10)')
        assert r.value == 10


class TestListAny:
    def test_any_true(self, run):
        r = run('return list.any([1, 2, 3], fn(x) -> x == 2)')
        assert r.value is True

    def test_any_false(self, run):
        r = run('return list.any([1, 2, 3], fn(x) -> x > 10)')
        assert r.value is False

    def test_any_empty(self, run):
        r = run('return list.any([], fn(x) -> true)')
        assert r.value is False


class TestListAll:
    def test_all_true(self, run):
        r = run('return list.all([2, 4, 6], fn(x) -> x % 2 == 0)')
        assert r.value is True

    def test_all_false(self, run):
        r = run('return list.all([2, 3, 6], fn(x) -> x % 2 == 0)')
        assert r.value is False

    def test_all_empty(self, run):
        r = run('return list.all([], fn(x) -> false)')
        assert r.value is True


class TestListZip:
    def test_zip_equal(self, run):
        r = run('return list.zip([1, 2, 3], ["a", "b", "c"])')
        assert r.value == [
            {"first": 1, "second": "a"},
            {"first": 2, "second": "b"},
            {"first": 3, "second": "c"},
        ]

    def test_zip_unequal(self, run):
        r = run('return list.zip([1, 2], ["a", "b", "c"])')
        assert r.value == [
            {"first": 1, "second": "a"},
            {"first": 2, "second": "b"},
        ]

    def test_zip_empty(self, run):
        r = run('return list.zip([], ["a"])')
        assert r.value == []


class TestListEnumerate:
    def test_enumerate(self, run):
        r = run('return list.enumerate(["a", "b", "c"])')
        assert r.value == [
            {"index": 0, "value": "a"},
            {"index": 1, "value": "b"},
            {"index": 2, "value": "c"},
        ]

    def test_enumerate_empty(self, run):
        r = run('return list.enumerate([])')
        assert r.value == []


class TestListGroupBy:
    def test_group_by(self, run):
        r = run(
            'let items = [{name: "a", tag: "x"}, {name: "b", tag: "y"}, {name: "c", tag: "x"}]\n'
            'return list.group_by(items, fn(i) -> i.tag)'
        )
        assert r.value == {
            "x": [{"name": "a", "tag": "x"}, {"name": "c", "tag": "x"}],
            "y": [{"name": "b", "tag": "y"}],
        }

    def test_group_by_empty(self, run):
        r = run('return list.group_by([], fn(x) -> "a")')
        assert r.value == {}


class TestListIndexOf:
    def test_index_of_found(self, run):
        r = run('return list.index_of([10, 20, 30], 20)')
        assert r.value == 1

    def test_index_of_not_found(self, run):
        r = run('return list.index_of([10, 20, 30], 99)')
        assert r.value is None

    def test_index_of_first(self, run):
        r = run('return list.index_of([1, 2, 1], 1)')
        assert r.value == 0

    def test_index_of_empty(self, run):
        r = run('return list.index_of([], 1)')
        assert r.value is None


class TestListUniqueBy:
    def test_unique_by(self, run):
        r = run(
            'let items = [{id: 1, name: "a"}, {id: 2, name: "b"}, {id: 1, name: "c"}]\n'
            'return list.unique_by(items, fn(x) -> x.id)'
        )
        assert r.value == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

    def test_unique_by_empty(self, run):
        r = run('return list.unique_by([], fn(x) -> x)')
        assert r.value == []

    def test_unique_by_all_same(self, run):
        r = run('return list.unique_by([1, 1, 1], fn(x) -> x)')
        assert r.value == [1]


# ===================================================================
# map.map / map.filter / map.from_entries / map.size
# ===================================================================

class TestMapMap:
    def test_map_values(self, run):
        r = run(
            'let m = {a: 1, b: 2, c: 3}\n'
            'return map.map(m, fn(k, v) -> v * 2)'
        )
        assert r.value == {"a": 2, "b": 4, "c": 6}

    def test_map_empty(self, run):
        r = run('return map.map({}, fn(k, v) -> v)')
        assert r.value == {}


class TestMapFilter:
    def test_filter_values(self, run):
        r = run(
            'let m = {a: 1, b: 2, c: 3}\n'
            'return map.filter(m, fn(k, v) -> v > 1)'
        )
        assert r.value == {"b": 2, "c": 3}

    def test_filter_by_key(self, run):
        r = run(
            'let m = {keep: 1, drop: 2}\n'
            'return map.filter(m, fn(k, v) -> k == "keep")'
        )
        assert r.value == {"keep": 1}

    def test_filter_empty(self, run):
        r = run('return map.filter({}, fn(k, v) -> true)')
        assert r.value == {}


class TestMapFromEntries:
    def test_from_entries(self, run):
        r = run(
            'let entries = [{key: "a", value: 1}, {key: "b", value: 2}]\n'
            'return map.from_entries(entries)'
        )
        assert r.value == {"a": 1, "b": 2}

    def test_from_entries_empty(self, run):
        r = run('return map.from_entries([])')
        assert r.value == {}

    def test_roundtrip(self, run):
        r = run(
            'let m = {x: 10, y: 20}\n'
            'return map.from_entries(map.entries(m))'
        )
        assert r.value == {"x": 10, "y": 20}


class TestMapSize:
    def test_size(self, run):
        r = run('return map.size({a: 1, b: 2, c: 3})')
        assert r.value == 3

    def test_size_empty(self, run):
        r = run('return map.size({})')
        assert r.value == 0


# ===================================================================
# text encoding utilities
# ===================================================================

class TestTextEncodeUrl:
    def test_encode_spaces(self, run):
        r = run('return text.encode_url("hello world")')
        assert r.value == "hello%20world"

    def test_encode_special(self, run):
        r = run('return text.encode_url("a&b=c")')
        assert r.value == "a%26b%3Dc"

    def test_encode_empty(self, run):
        r = run('return text.encode_url("")')
        assert r.value == ""


class TestTextDecodeUrl:
    def test_decode(self, run):
        r = run('return text.decode_url("hello%20world")')
        assert r.value == "hello world"

    def test_roundtrip(self, run):
        r = run('return text.decode_url(text.encode_url("a&b=c"))')
        assert r.value == "a&b=c"


class TestTextEncodeBase64:
    def test_encode(self, run):
        r = run('return text.encode_base64("hello")')
        assert r.value == "aGVsbG8="

    def test_encode_empty(self, run):
        r = run('return text.encode_base64("")')
        assert r.value == ""


class TestTextDecodeBase64:
    def test_decode(self, run):
        r = run('return text.decode_base64("aGVsbG8=")')
        assert r.value == "hello"

    def test_roundtrip(self, run):
        r = run('return text.decode_base64(text.encode_base64("test data"))')
        assert r.value == "test data"


# ===================================================================
# text pattern matching
# ===================================================================

class TestTextMatchPattern:
    def test_email_valid(self, run):
        r = run('return text.match_pattern("user@example.com", :email)')
        assert r.value is True

    def test_email_invalid(self, run):
        r = run('return text.match_pattern("not-an-email", :email)')
        assert r.value is False

    def test_url_valid(self, run):
        r = run('return text.match_pattern("https://example.com/path", :url)')
        assert r.value is True

    def test_iso_date_valid(self, run):
        r = run('return text.match_pattern("2024-01-15", :iso_date)')
        assert r.value is True

    def test_iso_date_invalid(self, run):
        r = run('return text.match_pattern("15/01/2024", :iso_date)')
        assert r.value is False

    def test_number_valid(self, run):
        r = run('return text.match_pattern("-3.14", :number)')
        assert r.value is True

    def test_unknown_pattern_errors(self, run):
        r = run('return text.match_pattern("test", :unknown_xyz)')
        assert r.type == "error"
        assert "unknown pattern" in r.error["message"]


class TestTextFindPattern:
    def test_find_emails(self, run):
        r = run('return text.find_pattern("Contact alice@test.com and bob@test.com", :email)')
        assert r.value == ["alice@test.com", "bob@test.com"]

    def test_find_urls(self, run):
        r = run('return text.find_pattern("Visit https://a.com and http://b.com/path", :url)')
        assert r.value == ["https://a.com", "http://b.com/path"]

    def test_find_dates(self, run):
        r = run('return text.find_pattern("Date: 2024-01-15 and 2024-02-20", :iso_date)')
        assert r.value == ["2024-01-15", "2024-02-20"]

    def test_find_none(self, run):
        r = run('return text.find_pattern("no emails here", :email)')
        assert r.value == []


# ===================================================================
# log
# ===================================================================

class TestLog:
    def test_log_returns_none(self, run):
        r = run('let x = log(42)\nreturn x')
        assert r.value is None

    def test_log_in_output(self, run):
        r = run('log("hello")\nlog(42)\nreturn 1')
        assert r.value == 1
        assert r.raw.get("logs") == ["hello", 42]

    def test_no_logs_when_empty(self, run):
        r = run('return 1')
        assert "logs" not in r.raw


# ===================================================================
# number.range
# ===================================================================

class TestNumberRange:
    def test_range_basic(self, run):
        r = run('return number.range(1, 5)')
        assert r.value == [1, 2, 3, 4, 5]

    def test_range_single(self, run):
        r = run('return number.range(3, 3)')
        assert r.value == [3]

    def test_range_negative(self, run):
        r = run('return number.range(-2, 2)')
        assert r.value == [-2, -1, 0, 1, 2]

    def test_range_empty(self, run):
        r = run('return number.range(5, 3)')
        assert r.value == []

    def test_range_too_large(self, run):
        r = run('return number.range(1, 20000)')
        assert r.type == "error"
        assert "too large" in r.error["message"]

    def test_range_with_map(self, run):
        r = run('return number.range(1, 3) |> list.map(fn(n) -> n * 10)')
        assert r.value == [10, 20, 30]
