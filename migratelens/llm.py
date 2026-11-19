"""Thin Gemini client: cache -> daily budget -> RPM throttle -> backoff -> API."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from migratelens.cache import Cache, make_key
from migratelens.throttle import DailyBudget, RetryableError, RpmThrottle, with_backoff

DEFAULT_MODEL = "gemini-3.5-flash-lite"
STATE_DIR = Path(".migratelens")


@dataclass
class LLMResult:
    text: str
    model: str
    tokens: int
    cached: bool


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, RetryableError):
        return True
    code = getattr(exc, "code", None)
    return code in (429, 500, 503)


class LLM:
    def __init__(
        self,
        model: str | None = None,
        rpm: int | None = None,
        daily_limit: int | None = None,
        cache: Cache | None = None,
        client=None,
        replay_only: bool = False,
    ):
        load_dotenv()
        self.model = model or os.environ.get("MIGRATELENS_MODEL", DEFAULT_MODEL)
        self.cache = cache or Cache(STATE_DIR / "cache.sqlite")
        self.throttle = RpmThrottle(rpm or int(os.environ.get("MIGRATELENS_RPM", "20")))
        self.budget = DailyBudget(
            daily_limit or int(os.environ.get("MIGRATELENS_DAILY_LIMIT", "500")),
            STATE_DIR / "budget.json",
        )
        self.replay_only = replay_only
        self._client = client
        self.api_calls = 0

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    def generate(self, prompt: str, tool_args: dict | None = None) -> LLMResult:
        key = make_key(prompt, self.model, tool_args)
        hit = self.cache.get(key)
        if hit is not None:
            return LLMResult(hit["text"], self.model, hit["tokens"], cached=True)
        if self.replay_only:
            raise RuntimeError("replay_only: no cached response for this prompt")

        def call():
            self.budget.consume()
            self.throttle.wait()
            return self._get_client().models.generate_content(model=self.model, contents=prompt)

        resp = with_backoff(call, is_retryable=_is_retryable)
        self.api_calls += 1
        tokens = getattr(getattr(resp, "usage_metadata", None), "total_token_count", 0) or 0
        value = {"text": resp.text or "", "tokens": tokens}
        self.cache.set(key, value)
        return LLMResult(value["text"], self.model, tokens, cached=False)


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Reply with one short sentence about migrations."
    llm = LLM()
    r = llm.generate(prompt)
    print(r.text.strip())
    print(f"[model={r.model} tokens={r.tokens} cached={r.cached}]", file=sys.stderr)


if __name__ == "__main__":
    main()
