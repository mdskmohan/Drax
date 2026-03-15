"""
Claude (Anthropic) API service.
Uses claude-sonnet-4-6 for main reasoning and claude-haiku-4-5 for fast tasks.
"""
import json
import anthropic
from app.config import settings

# Async Anthropic client
_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

MAIN_MODEL = "claude-sonnet-4-6"       # coaching, workouts, reports, meal plans
FAST_MODEL = "claude-haiku-4-5-20251001"  # meal parsing, quick replies, water tips


async def chat_completion(
    messages: list[dict],
    system: str = "",
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call Claude main model for reasoning/coaching tasks."""
    kwargs = {
        "model": model or MAIN_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = await _client.messages.create(**kwargs)
    return response.content[0].text


async def fast_completion(
    messages: list[dict],
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    """Call Claude Haiku for fast, cheap parsing tasks."""
    kwargs = {
        "model": FAST_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = await _client.messages.create(**kwargs)
    return response.content[0].text


async def json_completion(
    messages: list[dict],
    system: str = "",
    model: str | None = None,
    max_tokens: int = 1024,
    fast: bool = False,
) -> dict:
    """
    Get a JSON response from Claude.
    Appends a reminder to return valid JSON to the system prompt.
    """
    json_system = (system + "\n\nIMPORTANT: Respond with valid JSON only. No markdown fences.").strip()
    raw = await (fast_completion if fast else chat_completion)(
        messages=messages,
        system=json_system,
        model=model,
        max_tokens=max_tokens,
    )
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from surrounding text
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"raw": raw}
