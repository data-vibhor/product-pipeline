import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(text: str) -> str:
    return THINK_RE.sub("", text).strip()


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


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("retry-after")
    if header:
        try:
            return min(float(header) + 1, 90.0)
        except ValueError:
            pass
    return min(15.0 * (attempt + 1), 90.0)


def post_with_retry(
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: float = 120.0,
    retries: int = 4,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    for attempt in range(retries + 1):
        response = httpx.post(url, headers=headers, json=json, timeout=timeout)
        if response.status_code != 429 or attempt == retries:
            response.raise_for_status()
            return response
        wait = _retry_wait(response, attempt)
        print(f"Rate limited, waiting {wait:.0f}s ...", file=sys.stderr, flush=True)
        sleep(wait)
    raise RuntimeError("unreachable")


class OllamaClient:
    def __init__(
        self,
        model: str | None = None,
        host: str = "http://localhost:11434",
        timeout: float = 600.0,
        num_ctx: int = 8192,
    ):
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:8b")
        self.host, self.timeout, self.num_ctx = host, timeout, num_ctx

    def chat(self, system: str, user: str) -> str:
        r = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "options": {"num_ctx": self.num_ctx},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return strip_thinking(r.json()["message"]["content"])


class GroqClient:
    def __init__(self, model: str = "openai/gpt-oss-120b", timeout: float = 120.0):
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to .env")
        self.key, self.model, self.timeout = key, model, timeout

    def chat(self, system: str, user: str) -> str:
        r = post_with_retry(
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
        return r.json()["choices"][0]["message"]["content"]


def get_client(name: str) -> LLM:
    load_env()
    if name == "ollama":
        return OllamaClient()
    if name == "groq":
        return GroqClient()
    raise ValueError(f"Unknown llm '{name}'")
