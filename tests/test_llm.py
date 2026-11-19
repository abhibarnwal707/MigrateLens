import pytest

from migratelens.cache import Cache
from migratelens.llm import LLM


class FakeResp:
    text = "hello"

    class usage_metadata:  # noqa: N801
        total_token_count = 7


class FakeModels:
    def __init__(self):
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        return FakeResp()


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


def make(tmp_path, monkeypatch, **kw):
    monkeypatch.chdir(tmp_path)
    client = FakeClient()
    llm = LLM(
        model="m",
        rpm=1000,
        daily_limit=100,
        cache=Cache(tmp_path / "c.sqlite"),
        client=client,
        **kw,
    )
    return llm, client


def test_second_call_is_cached(tmp_path, monkeypatch):
    llm, client = make(tmp_path, monkeypatch)
    first = llm.generate("hi")
    second = llm.generate("hi")
    assert (first.cached, second.cached) == (False, True)
    assert second.text == "hello" and client.models.calls == 1


def test_replay_only_never_calls_api(tmp_path, monkeypatch):
    llm, client = make(tmp_path, monkeypatch, replay_only=True)
    with pytest.raises(RuntimeError):
        llm.generate("unseen")
    assert client.models.calls == 0
