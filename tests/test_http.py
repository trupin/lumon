"""Tests for Lumon http.* built-ins with MockHTTP."""

import pytest

from tests.conftest import MockHTTP


@pytest.fixture
def run(runner):
    def _run(code, *, http=None):
        return runner.run(code, http=http)
    return _run


class TestHttpGet:
    def test_get_success(self, run):
        http = MockHTTP({"https://example.com": "<html>hello</html>"})
        r = run('return http.get("https://example.com")', http=http)
        assert r.tag_name == "ok"
        assert r.tag_value == "<html>hello</html>"

    def test_get_unreachable(self, run):
        http = MockHTTP()
        r = run('return http.get("https://missing.com")', http=http)
        assert r.tag_name == "error"

    def test_get_blacklisted(self, run):
        http = MockHTTP(
            responses={"https://evil.com": "bad stuff"},
            blacklist=["https://evil.com"],
        )
        r = run('return http.get("https://evil.com")', http=http)
        assert r.tag_name == "error"

    def test_blacklist_error_indistinguishable(self, run):
        """Blacklisted URLs return :error just like unreachable ones."""
        http = MockHTTP(blacklist=["https://blocked.com"])
        r_blocked = run('return http.get("https://blocked.com")', http=http)
        r_missing = run('return http.get("https://nonexistent.com")', http=http)
        assert r_blocked.tag_name == "error"
        assert r_missing.tag_name == "error"

    def test_multiple_gets(self, run):
        http = MockHTTP({
            "https://a.com": "aaa",
            "https://b.com": "bbb",
        })
        r = run(
            'let a = http.get("https://a.com")\n'
            'let b = http.get("https://b.com")\n'
            'return [a, b]',
            http=http,
        )
        assert r.value == [
            {"tag": "ok", "value": "aaa"},
            {"tag": "ok", "value": "bbb"},
        ]

    def test_http_in_match(self, run):
        http = MockHTTP({"https://api.com": "data"})
        r = run(
            'let result = http.get("https://api.com")\n'
            'return match result\n'
            '  :ok(body) -> body\n'
            '  :error(m) -> "failed"',
            http=http,
        )
        assert r.value == "data"

    def test_http_error_in_match(self, run):
        http = MockHTTP()
        r = run(
            'let result = http.get("https://missing.com")\n'
            'return match result\n'
            '  :ok(body) -> body\n'
            '  :error(m) -> "failed: " + m',
            http=http,
        )
        assert r.value.startswith("failed:")

    def test_http_in_pipe_chain(self, run):
        http = MockHTTP({"https://api.com": "line1\nline2\nline3"})
        r = run(
            'let result = http.get("https://api.com")\n'
            'return match result\n'
            '  :ok(body) -> body |> text.split("\\n") |> list.length\n'
            '  :error(_) -> 0',
            http=http,
        )
        assert r.value == 3
