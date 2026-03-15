"""
DeepSeek API service.
DeepSeek uses an OpenAI-compatible API, so we use the openai client
pointed at the DeepSeek base URL.
"""
import json
from openai import AsyncOpenAI
from app.config import settings

# Main reasoning client (DeepSeek V3)
_main_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)

# Fast parsing client (same API, lighter usage)
_fast_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    """Call DeepSeek main model for reasoning tasks."""
    kwargs = {
        "model": model or settings.deepseek_main_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await _main_client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def fast_completion(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 512,
    json_mode: bool = False,
) -> str:
    """Call DeepSeek fast model for quick parsing tasks."""
    kwargs = {
        "model": settings.deepseek_fast_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await _fast_client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def parse_json_response(raw: str) -> dict:
    """Extract JSON from a model response that might have markdown fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
