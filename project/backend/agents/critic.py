"""
Critic Agent
Reads: question, draft, revision_count
Writes: critique, quality_score, final_answer (if passing), agent_log
Model: fast
"""

import re
from ..models.fast import fast_model
from ..config import MIN_SCORE, MAX_REVISIONS


_SYSTEM = (
    "You are a rigorous academic critic. Evaluate the answer and reply ONLY in this format:\n"
    "Score: X/10\n"
    "Strengths: <one sentence>\n"
    "Weaknesses: <one sentence>\n"
    "Verdict: PASS or REVISE"
)


def critic_node(state: dict) -> dict:
    result = fast_model(
        system=_SYSTEM,
        user=f"Question: {state['question']}\n\nAnswer:\n{state['draft']}",
        max_tokens=150,
    )

    try:
        score = int(re.search(r"Score:\s*(\d+)", result).group(1))
    except Exception:
        score = 7

    log_entry = f"[Critic] Score {score}/10"
    updates: dict = {
        "critique"     : result,
        "quality_score": score,
        "agent_log"    : state.get("agent_log", []) + [log_entry],
    }

    passes = score >= MIN_SCORE or state.get("revision_count", 0) >= MAX_REVISIONS
    if passes:
        updates["final_answer"] = state["draft"]

    return updates
