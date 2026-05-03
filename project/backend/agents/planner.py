"""
Planner Agent
Reads: question, memory_context
Writes: subtasks, agent_log
Model: balanced
"""

import json
import re
from ..models.balanced import balanced_model


def planner_node(state: dict) -> dict:
    context = ""
    if state.get("memory_context"):
        context = "\n\nRelevant past answers:\n" + "\n".join(
            f"  - {c[:120]}" for c in state["memory_context"]
        )

    result = balanced_model(
        system=(
            "You are a task planner. Given a question, output a JSON array of "
            "3-4 specific research subtasks. Output ONLY the array.\n"
            'Example: ["Explain X", "Find examples of Y", "Compare Z"]'
        ),
        user=state["question"] + context,
        max_tokens=200,
    )
    match = re.search(r"\[.*?\]", result, re.DOTALL)
    try:
        subtasks = json.loads(match.group()) if match else ["Research the topic", "Find examples", "Summarise findings"]
    except Exception:
        subtasks = ["Research the topic", "Find examples", "Summarise findings"]

    return {
        "subtasks" : subtasks,
        "agent_log": state.get("agent_log", []) + [f"[Planner] {len(subtasks)} subtasks"],
    }
