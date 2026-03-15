"""
Drax LangGraph — assembles nodes and edges into a runnable graph.

Flow:
  START
    → load_user          (fetch user from DB)
    → supervisor         (classify intent with fast LLM)
    → [conditional]      (route to the right agent node)
    → agent_node         (do the work, set response + chain_to)
    → chain_check        (decide: chain to another node or END)
    → [conditional]      (nudge_water | END)
  END
"""
from langgraph.graph import StateGraph, START, END

from app.graph.state import DraxState
from app.graph.supervisor import supervisor_node, route_from_supervisor
from app.graph.nodes import (
    load_user_node,
    log_meal_node,
    log_water_node,
    get_workout_node,
    log_weight_node,
    get_progress_node,
    get_motivation_node,
    get_plan_node,
    report_pain_node,
    general_node,
    chain_check_node,
    water_nudge_node,
    route_chain,
)


def build_graph():
    """Build and compile the Drax agent graph."""
    g = StateGraph(DraxState)

    # ── Add all nodes ──────────────────────────────────────────────────────────
    g.add_node("load_user",     load_user_node)
    g.add_node("supervisor",    supervisor_node)

    # Agent nodes (one per intent)
    g.add_node("log_meal",      log_meal_node)
    g.add_node("log_water",     log_water_node)
    g.add_node("get_workout",   get_workout_node)
    g.add_node("log_weight",    log_weight_node)
    g.add_node("get_progress",  get_progress_node)
    g.add_node("get_motivation",get_motivation_node)
    g.add_node("get_plan",      get_plan_node)
    g.add_node("report_pain",   report_pain_node)
    g.add_node("general",       general_node)

    # Chaining nodes
    g.add_node("chain_check",   chain_check_node)
    g.add_node("nudge_water",   water_nudge_node)

    # ── Edges ──────────────────────────────────────────────────────────────────

    # 1. Always start by loading the user
    g.add_edge(START, "load_user")

    # 2. load_user → supervisor
    g.add_edge("load_user", "supervisor")

    # 3. supervisor → correct agent node (conditional)
    g.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "log_meal":       "log_meal",
            "log_water":      "log_water",
            "get_workout":    "get_workout",
            "log_weight":     "log_weight",
            "get_progress":   "get_progress",
            "get_motivation": "get_motivation",
            "get_plan":       "get_plan",
            "report_pain":    "report_pain",
            "general":        "general",
        },
    )

    # 4. All agent nodes → chain_check
    for node in ["log_meal", "log_water", "get_workout", "log_weight",
                 "get_progress", "get_motivation", "get_plan",
                 "report_pain", "general"]:
        g.add_edge(node, "chain_check")

    # 5. chain_check → nudge_water (if chain_to=="nudge_water") or END
    g.add_conditional_edges(
        "chain_check",
        route_chain,
        {
            "nudge_water": "nudge_water",
            "__end__":     END,
        },
    )

    # 6. nudge_water → END
    g.add_edge("nudge_water", END)

    return g.compile()


# ── Singleton — compiled once at import time ───────────────────────────────────
drax_graph = build_graph()
