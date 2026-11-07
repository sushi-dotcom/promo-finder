"""Swappable model layer. Every provider has the same one method: complete(prompt) -> str.

To plug in a different model, add one small class with a `complete` method and register
it in make_llm(). Nothing else in the pipeline changes.
"""
import os
import time

import requests


class LLM:
    name = "base"

    def complete(self, prompt: str) -> str:
        raise NotImplementedError


class APIConfigError(Exception):
    """Wrong model name or key. Deliberately NOT a RuntimeError, so judge.py does not
    swallow it batch by batch: it stops the whole run (caught in run.py)."""


def _post_with_retry(url, payload, headers=None, tries=3):
    """POST with a simple back-off for rate limits (429), server errors (5xx) and
    network problems (timeouts, dropped connections).

    Temporary problems raise RuntimeError after the last try, so judge.py falls back to
    rules for that batch. Config problems (400/401/403/404) raise APIConfigError at once.
    """
    timeout = float(os.environ.get("LLM_TIMEOUT", "300"))   # seconds to wait for a reply
    for attempt in range(tries):
        try:
            r = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
            if attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"network problem after {tries} tries: {type(err).__name__}")
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 401, 403, 404):
            raise APIConfigError(f"API error {r.status_code} (check the model name and API key): "
                                 f"{r.text[:300]}")
        if r.status_code in (429, 500, 502, 503, 504) and attempt < tries - 1:
            time.sleep(5 * (attempt + 1))
            continue
        raise RuntimeError(f"API error {r.status_code}: {r.text[:300]}")


class GeminiLLM(LLM):
    """Google Gemini via its REST API. Free key: Google AI Studio. Set GEMINI_API_KEY."""

    def __init__(self, model=None):
        self.key = os.environ.get("GEMINI_API_KEY")
        if not self.key:
            raise RuntimeError("GEMINI_API_KEY is not set (or use --provider rules).")
        # Model names change over time; override with --model or GEMINI_MODEL if needed.
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.name = f"gemini:{self.model}"

    def complete(self, prompt):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        payload = {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0.2,
                                        "responseMimeType": "application/json"}}
        # Key goes in a header, not the URL, so it never shows up in logs or error messages.
        data = _post_with_retry(url, payload, {"x-goog-api-key": self.key})
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OpenAICompatibleLLM(LLM):
    """Any OpenAI-style chat API: Groq, OpenAI, or a company's own endpoint.

    Set LLM_BASE_URL (e.g. https://api.groq.com/openai/v1), LLM_API_KEY and --model.
    """

    def __init__(self, model=None):
        self.base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        self.key = os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL")
        if not (self.base and self.key and self.model):
            raise RuntimeError("Set LLM_BASE_URL, LLM_API_KEY and a model (--model or LLM_MODEL).")
        self.name = f"openai-compatible:{self.model}"

    def complete(self, prompt):
        payload = {"model": self.model, "temperature": 0.2,
                   "messages": [{"role": "user", "content": prompt}]}
        data = _post_with_retry(f"{self.base}/chat/completions", payload,
                                {"Authorization": f"Bearer {self.key}"})
        return data["choices"][0]["message"]["content"]


class RulesOnly(LLM):
    """No model at all: the pipeline uses its rules-based scores. Always works offline."""
    name = "rules-only"

    def complete(self, prompt):
        return None


def make_llm(provider: str, model=None) -> LLM:
    providers = {"gemini": GeminiLLM, "openai": OpenAICompatibleLLM, "rules": RulesOnly}
    if provider not in providers:
        raise ValueError(f"Unknown provider '{provider}'. Choose from {list(providers)}.")
    return providers[provider]() if provider == "rules" else providers[provider](model)
