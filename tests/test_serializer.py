"""Tests for lumon.serializer — serialize and deserialize round-trips."""

from __future__ import annotations

from lumon.serializer import deserialize, serialize
from lumon.values import LumonTag


class TestSerialize:
    def test_string_passthrough(self) -> None:
        assert serialize("hello") == "hello"

    def test_int_passthrough(self) -> None:
        assert serialize(42) == 42

    def test_float_passthrough(self) -> None:
        assert serialize(3.14) == 3.14

    def test_bool_passthrough(self) -> None:
        assert serialize(True) is True

    def test_none_passthrough(self) -> None:
        assert serialize(None) is None

    def test_list(self) -> None:
        assert serialize([1, "a", None]) == [1, "a", None]

    def test_dict(self) -> None:
        assert serialize({"a": 1, "b": "c"}) == {"a": 1, "b": "c"}

    def test_tag_no_payload(self) -> None:
        assert serialize(LumonTag("ok")) == {"tag": "ok"}

    def test_tag_with_payload(self) -> None:
        assert serialize(LumonTag("error", "oops")) == {"tag": "error", "value": "oops"}

    def test_nested_tag_in_list(self) -> None:
        result = serialize([LumonTag("ok"), LumonTag("error", "x")])
        assert result == [{"tag": "ok"}, {"tag": "error", "value": "x"}]

    def test_nested_tag_in_map(self) -> None:
        result = serialize({"status": LumonTag("ok")})
        assert result == {"status": {"tag": "ok"}}


class TestDeserialize:
    def test_string_passthrough(self) -> None:
        assert deserialize("hello") == "hello"

    def test_int_passthrough(self) -> None:
        assert deserialize(42) == 42

    def test_none_passthrough(self) -> None:
        assert deserialize(None) is None

    def test_bool_passthrough(self) -> None:
        assert deserialize(True) is True

    def test_tag_no_payload(self) -> None:
        result = deserialize({"tag": "ok"})
        assert isinstance(result, LumonTag)
        assert result.name == "ok"
        assert result.payload is None

    def test_tag_with_payload(self) -> None:
        result = deserialize({"tag": "error", "value": "oops"})
        assert isinstance(result, LumonTag)
        assert result.name == "error"
        assert result.payload == "oops"

    def test_tag_with_nested_payload(self) -> None:
        result = deserialize({"tag": "ok", "value": {"tag": "inner"}})
        assert isinstance(result, LumonTag)
        assert isinstance(result.payload, LumonTag)
        assert result.payload.name == "inner"

    def test_map_not_tag(self) -> None:
        result = deserialize({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_map_with_extra_keys_not_tag(self) -> None:
        result = deserialize({"tag": "ok", "extra": True})
        assert result == {"tag": "ok", "extra": True}

    def test_list(self) -> None:
        result = deserialize([{"tag": "ok"}, 42])
        assert isinstance(result, list)
        assert isinstance(result[0], LumonTag)
        assert result[1] == 42

    def test_map_with_nested_tag(self) -> None:
        result = deserialize({"status": {"tag": "ok"}})
        assert isinstance(result, dict)
        assert isinstance(result["status"], LumonTag)


class TestRoundTrip:
    def test_tag_round_trip(self) -> None:
        original = LumonTag("ok", "done")
        assert deserialize(serialize(original)) == original

    def test_nested_round_trip(self) -> None:
        original = [LumonTag("ok"), {"key": LumonTag("err", "x")}]
        result = deserialize(serialize(original))
        assert result == original
