"""
Writer Agent
Reads: question, research, critique (if revision), revision_count
Writes: draft, agent_log
Model: balanced
"""

from ..models.balanced import balanced_model


_SYSTEM = """You are an expert academic writer for university students.
Synthesise the research notes into a clear, well-structured answer.
Structure: brief introduction → main points (with evidence) → concise conclusion.
Write for a first-year student: clear language, no unexplained jargon."""


def writer_node(state: dict) -> dict:
    notes = "\n\n".join(
        f"• {task}:\n  {finding}"
        for task, finding in state.get("research", {}).items()
    )

    critique_section = ""
    if state.get("critique") and state.get("revision_count", 0) > 0:
        critique_section = f"\n\nPrevious feedback to address:\n{state['critique']}"

    draft = balanced_model(
        system=_SYSTEM,
        user=(
            f"Question: {state['question']}\n\n"
            f"Research notes:\n{notes}"
            f"{critique_section}"
        ),
        max_tokens=900,
    )

    rev = state.get("revision_count", 0)
    return {
        "draft"         : draft,
        "revision_count": rev + 1,
        "agent_log"     : state.get("agent_log", []) + [f"[Writer] Draft #{rev + 1} written"],
    }
