from pipeline.llm import OllamaClient, strip_thinking


def test_strip_thinking_removes_block():
    raw = "<think>reasoning here</think>\n\n## Problem\nText"
    assert strip_thinking(raw) == "## Problem\nText"


def test_strip_thinking_leaves_plain_text():
    assert strip_thinking("plain") == "plain"


def test_ollama_model_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    assert OllamaClient().model == "qwen2.5:7b"


def test_ollama_default_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert OllamaClient().model == "qwen3:8b"
