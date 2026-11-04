"""
CURATOR — LLM Client Abstraction
Unified interface over Anthropic Claude and OpenAI GPT.
Swap provider via ACTIVE_LLM env var without changing pipeline code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str,
                       max_tokens: int = 1000, temperature: float = 0.1) -> str: ...

    @abstractmethod
    async def complete_with_history(self, system: str,
                                    messages: list[dict[str, str]],
                                    max_tokens: int = 1000,
                                    temperature: float = 0.1) -> str: ...


#  Anthropic Client

class AnthropicClient(BaseLLMClient):
    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete(self, system: str, user: str,
                       max_tokens: int = 1000, temperature: float = 0.1) -> str:
        msg = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete_with_history(self, system: str,
                                    messages: list[dict[str, str]],
                                    max_tokens: int = 1000,
                                    temperature: float = 0.1) -> str:
        msg = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )
        return msg.content[0].text


#  OpenAI Client

class OpenAIClient(BaseLLMClient):
    def __init__(self) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete(self, system: str, user: str,
                       max_tokens: int = 1000, temperature: float = 0.1) -> str:
        resp = await self._client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete_with_history(self, system: str,
                                    messages: list[dict[str, str]],
                                    max_tokens: int = 1000,
                                    temperature: float = 0.1) -> str:
        full = [{"role": "system", "content": system}] + messages
        resp = await self._client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=full,
        )
        return resp.choices[0].message.content or ""


#  Offline extractive client (no network, deterministic)

class OfflineExtractiveClient(BaseLLMClient):
    """Fallback used when no API key is configured.  The router prompt gets
    a rule-based JSON classification; generation returns an extractive
    summary of the retrieved context with [BlockID] citations, so the whole
    pipeline remains testable offline."""

    _PATHWAY = re.compile(r"\b(before|prerequisite|prepare|order|önce|ön ?koşul|sıra)\b", re.I)
    _RELATION = re.compile(r"\b(relate|connect|link|between|ilişki|bağlantı|arasında)\b", re.I)
    _ADVICE = re.compile(r"\b(should i|advice|recommend|review|öner|tavsiye|tekrar)\b", re.I)

    async def complete(self, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.1) -> str:
        if "query classifier" in system:
            qt = ("pathway" if self._PATHWAY.search(user) else "relational" if self._RELATION.search(user)
                  else "advisory" if self._ADVICE.search(user) else "factual")
            ents = re.findall(r"\b[YR]\d[A-Z0-9]+\b", user)
            return json.dumps({"query_type": qt, "entities": ents[:5]})
        return self._extract(system, user)

    async def complete_with_history(self, system: str, messages: list[dict[str, str]],
                                    max_tokens: int = 1000, temperature: float = 0.1) -> str:
        return self._extract(system, messages[-1]["content"] if messages else "")

    @staticmethod
    def _extract(system: str, query: str) -> str:
        tr = "MÜFREDAT BAĞLAMI" in system
        blocks = re.findall(r"\[\d+\] Source: (\S+) \(score: [0-9.]+\)\n(.+)", system)
        if not blocks:
            return ("Bağlamda yeterli bilgi bulunamadı." if tr else
                    "The retrieved curriculum context does not contain enough information.")
        seen, lines = set(), []
        for i, (src, first_line) in enumerate(blocks, start=1):
            if src in seen:
                continue
            seen.add(src)
            lines.append(f"{len(seen)}. {first_line.strip()} [{src}]")
            if len(seen) >= 5:
                break
        head = ("Çevrimdışı mod (LLM anahtarı yok) — en ilgili müfredat kayıtları:" if tr else
                "Offline mode (no LLM key configured) — most relevant curriculum records:")
        return head + "\n\n" + "\n".join(lines)


#  Factory

_client_cache: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    global _client_cache
    if _client_cache is None:
        provider = settings.active_llm
        try:
            if provider == "anthropic" and settings.anthropic_api_key:
                _client_cache = AnthropicClient()
            elif provider == "openai" and settings.openai_api_key:
                _client_cache = OpenAIClient()
            else:
                provider = "offline"
        except Exception as exc:          # SDK missing or misconfigured
            logger.warning("llm.client_failed", provider=provider, error=str(exc))
            provider = "offline"
        if provider == "offline":
            _client_cache = OfflineExtractiveClient()
        logger.info("llm.client_created", provider=provider)
    return _client_cache
