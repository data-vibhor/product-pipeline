import httpx
import pytest

from pipeline import llm


def make_response(status, headers=None):
    return httpx.Response(
        status,
        headers=headers or {},
        request=httpx.Request("POST", "http://x"),
        json={"ok": True},
    )


def test_retries_then_succeeds(monkeypatch):
    responses = [make_response(429, {"retry-after": "2"}), make_response(200)]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: responses.pop(0))
    waits = []
    r = llm.post_with_retry("http://x", sleep=waits.append)
    assert r.status_code == 200
    assert waits == [3.0]


def test_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: make_response(429))
    waits = []
    with pytest.raises(httpx.HTTPStatusError):
        llm.post_with_retry("http://x", retries=2, sleep=waits.append)
    assert len(waits) == 2


def test_other_errors_are_not_retried(monkeypatch):
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return make_response(500)

    monkeypatch.setattr(llm.httpx, "post", fake)
    with pytest.raises(httpx.HTTPStatusError):
        llm.post_with_retry("http://x", sleep=lambda s: None)
    assert len(calls) == 1
