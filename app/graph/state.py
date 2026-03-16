"""
Drax Graph State.
This TypedDict is the single object that flows through every node in the graph.
Each node reads from it and returns a partial update dict.
"""
from __future__ import annotations
from typing import Any, Literal
from typing_extensions import TypedDict


# All valid intents the supervisor can classify
Intent = Literal[
    "log_meal",
    "log_water",
    "get_workout",
    "log_weight",
    "get_progress",
    "get_motivation",
    "get_plan",
    "report_pain",
    "scan_equipment",
    "general",
]


class DraxState(TypedDict, total=False):
    # ── Input ──────────────────────────────────────────────────────────────────
    user_id: int
    user_input: str               # raw text from the Telegram message
    context: dict                 # extra context from the handler (meal_type, etc.)

    # ── User profile (loaded once per invoke) ─────────────────────────────────
    user: Any                     # app.models.user.User instance

    # ── Routing ───────────────────────────────────────────────────────────────
    intent: Intent                # set by supervisor node

    # ── Agent outputs ─────────────────────────────────────────────────────────
    nutrition_data: dict          # parsed meal nutrition
    workout_plan: dict            # generated workout
    water_status: dict            # hydration progress
    progress_data: dict           # weight/stats
    pain_assessment: dict         # injury assessment

    # ── Final response sent back to the Telegram handler ─────────────────────
    response: str                 # formatted text for Telegram
    response_data: dict           # structured data (for keyboards, inline menus)

    # ── Multi-step chaining ───────────────────────────────────────────────────
    # After the primary agent runs, should the graph chain to another agent?
    # e.g., after logging a meal, chain to hydration check if water is low
    chain_to: str                 # next intent, or "" to stop
