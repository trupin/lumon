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
