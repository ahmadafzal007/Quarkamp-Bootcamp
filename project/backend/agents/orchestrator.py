"""
Orchestrator Agent
Reads: question, skill (from URL /skill command)
Writes: route, agent_log
Model: fast (classification only)
"""

from ..models.fast import fast_model
from ..config import SKILLS


def orchestrator_node(state: dict) -> dict:
    question = state["question"]
    skill    = state.get("skill", "")

    # If skill is explicitly set (e.g. /research), use it
    if skill and skill in SKILLS:
        route = skill
    else:
        result = fast_model(
            system=(
                "You are a routing agent. Classify the question into ONE of: "
                "research, plan, critique, summarize. "
                "Reply with ONE word only."
            ),
            user=question,
            max_tokens=10,
        )
        route = result.strip().lower()
        if route not in SKILLS:
            route = "research"

    return {
        "route"    : route,
        "agent_log": state.get("agent_log", []) + [f"[Orchestrator] Route → {route}"],
    }
