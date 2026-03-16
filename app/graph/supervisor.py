"""
Supervisor Node — classifies user intent and routes to the correct agent node.
Uses the fast LLM model (cheap, quick) since this is just classification.
"""
from __future__ import annotations

from app.graph.state import DraxState, Intent
from app.services.llm import llm

_SYSTEM = """You are an intent classifier for a fitness coaching bot.
Classify the user message into exactly one of these intents:

- log_meal      → user is describing food they ate
- log_water     → user mentions drinking water/liquid
- get_workout   → user wants today's workout or exercise plan
- log_weight    → user is reporting their current weight
- get_progress  → user wants to see their progress, stats, or weekly report
- get_motivation → user wants motivation, a quote, or pump-up message
- get_plan      → user wants their full daily plan (meals + workout together)
- report_pain   → user reports pain, injury, soreness, or discomfort
- general       → anything else (greetings, questions, help)

Return JSON: {"intent": "<intent>", "confidence": 0.0-1.0}"""


async def supervisor_node(state: DraxState) -> dict:
    """Classify intent from user_input. Always runs first."""
    user_input = state.get("user_input", "")

    # Fast rule-based pre-checks (no LLM needed for obvious cases)
    lower = user_input.lower()
    if any(w in lower for w in ["ml", "glass", "bottle", "drank", "water"]):
        return {"intent": "log_water"}
    if any(w in lower for w in ["workout", "exercise", "gym", "training"]):
        return {"intent": "get_workout"}
    if any(w in lower for w in ["motivat", "inspire", "pump", "quote"]):
        return {"intent": "get_motivation"}
    if any(w in lower for w in ["pain", "hurt", "sore", "injury", "ache"]):
        return {"intent": "report_pain"}
    if any(w in lower for w in ["progress", "report", "stats", "how am i"]):
        return {"intent": "get_progress"}

    # LLM classification for ambiguous inputs
    result = await llm.json(
        messages=[{"role": "user", "content": user_input}],
        system=_SYSTEM,
        fast=True,
        max_tokens=60,
    )
    intent = result.get("intent", "general")

    # Validate intent is one of the known values
    valid = {"log_meal","log_water","get_workout","log_weight","get_progress",
             "get_motivation","get_plan","report_pain","general"}
    if intent not in valid:
        intent = "general"

    return {"intent": intent}


def route_from_supervisor(state: DraxState) -> str:
    """
    Conditional edge function — LangGraph calls this after the supervisor
    to decide which node to visit next.
    Returns the node name as a string.
    """
    return state.get("intent", "general")
