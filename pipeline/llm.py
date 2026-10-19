import os
from pathlib import Path
from typing import Protocol

import httpx


class LLM(Protocol):
    def chat(self, system: str, user: str) -> str: ...


def load_env(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class OllamaClient:
    def __init__(
        self,
        model: str = "qwen2.5:7b",
        host: str = "http://localhost:11434",
        timeout: float = 600.0,
    ):
        self.model, self.host, self.timeout = model, host, timeout

    def chat(self, system: str, user: str) -> str:
        r = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


class GroqClient:
    def __init__(self, model: str = "openai/gpt-oss-120b", timeout: float = 120.0):
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to .env")
        self.key, self.model, self.timeout = key, model, timeout

    def chat(self, system: str, user: str) -> str:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def get_client(name: str) -> LLM:
    load_env()
    if name == "ollama":
        return OllamaClient()
    if name == "groq":
        return GroqClient()
    raise ValueError(f"Unknown llm '{name}'")
