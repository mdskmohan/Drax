"""
Unified LLM service for Drax.
Supports OpenAI, Claude (Anthropic), and DeepSeek — swap via LLM_PROVIDER in .env.

Usage (same interface regardless of provider):
    from app.services.llm import llm
    text = await llm.chat(messages, system="You are a coach...")
    data = await llm.json(messages, system="...")
    text = await llm.fast(messages, system="...")
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ── Default models per provider ────────────────────────────────────────────────
_DEFAULTS = {
    "claude": {
        "main": "claude-sonnet-4-6",
        "fast": "claude-haiku-4-5-20251001",
    },
    "openai": {
        "main": "gpt-4o",
        "fast": "gpt-4o-mini",
    },
    "deepseek": {
        "main": "deepseek-chat",
        "fast": "deepseek-chat",
    },
}


class LLMService:
    """
    Provider-agnostic LLM wrapper.
    Internally routes to Anthropic SDK (Claude) or OpenAI SDK (OpenAI/DeepSeek).
    DeepSeek uses an OpenAI-compatible API so the same client works with a
    different base_url.
    """

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        defaults = _DEFAULTS.get(self.provider, _DEFAULTS["claude"])
        self.main_model = settings.llm_main_model or defaults["main"]
        self.fast_model = settings.llm_fast_model or defaults["fast"]
        self._openai_client = None
        self._anthropic_client = None

    # ── Public interface ───────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Main model — coaching, planning, reports."""
        return await self._call(
            messages, system, self.main_model, temperature, max_tokens, json_mode=False
        )

    async def fast(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """Fast/cheap model — parsing, quick replies."""
        return await self._call(
            messages, system, self.fast_model, temperature, max_tokens, json_mode=False
        )

    async def json(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 1024,
        fast: bool = False,
    ) -> dict:
        """Return parsed JSON dict. Uses fast model when fast=True."""
        model = self.fast_model if fast else self.main_model
        json_system = (
            system + "\n\nIMPORTANT: Respond with valid JSON only. No explanation, no markdown."
        ).strip()
        raw = await self._call(
            messages, json_system, model, temperature=0.3, max_tokens=max_tokens, json_mode=True
        )
        return _parse_json(raw)

    async def vision(self, image_bytes: bytes, prompt: str, system: str = "") -> str:
        """Analyze an image. Uses main model (supports vision for all providers)."""
        import base64
        b64 = base64.b64encode(image_bytes).decode()

        if self.provider == "claude":
            client = self._get_anthropic_client()
            kwargs: dict = {
                "model": self.main_model,
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            }
            if system:
                kwargs["system"] = system
            response = await client.messages.create(**kwargs)
            return response.content[0].text
        else:
            # OpenAI and DeepSeek vision-compatible format
            client = self._get_openai_client()
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            })
            response = await client.chat.completions.create(
                model=self.main_model,
                messages=full_messages,
                max_tokens=1024,
            )
            return response.choices[0].message.content

    # ── Internal routing ───────────────────────────────────────────────────────

    async def _call(
        self,
        messages: list[dict],
        system: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        if self.provider == "claude":
            return await self._call_anthropic(messages, system, model, temperature, max_tokens)
        else:
            # OpenAI and DeepSeek both use the OpenAI client
            return await self._call_openai(messages, system, model, temperature, max_tokens, json_mode)

    async def _call_anthropic(
        self,
        messages: list[dict],
        system: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        client = self._get_anthropic_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def _call_openai(
        self,
        messages: list[dict],
        system: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        client = self._get_openai_client()
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    # ── Lazy client initialisation ─────────────────────────────────────────────

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set in .env")
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )
        return self._anthropic_client

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            if self.provider == "deepseek":
                if not settings.deepseek_api_key:
                    raise ValueError("DEEPSEEK_API_KEY is not set in .env")
                self._openai_client = AsyncOpenAI(
                    api_key=settings.deepseek_api_key,
                    base_url="https://api.deepseek.com/v1",
                )
            else:
                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is not set in .env")
                self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON, with fallback regex extraction."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.warning(f"Failed to parse JSON from LLM response: {raw[:200]}")
        return {"raw": raw}


# ── Singleton ──────────────────────────────────────────────────────────────────
llm = LLMService()
