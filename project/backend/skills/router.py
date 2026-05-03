"""
Skill router — maps slash commands to pipeline configurations.

/research <question>  → route=research, full pipeline
/plan <question>      → route=plan, full pipeline
/critique <text>      → route=critique, skip Researcher
/summarize <text>     → route=summarize, skip Researcher
/memory <query>       → direct ChromaDB search, no pipeline
/help                 → list skills
"""

import json
from ..config import SKILLS
from ..plugins.memory import memory_retrieve


def route_skill(raw_input: str) -> dict:
    """
    Parse the user's input and return:
    {
        "skill": str,
        "question": str,
        "is_pipeline": bool,   # False for /memory and /help
        "response": str | None # immediate response for non-pipeline skills
    }
    """
    raw = raw_input.strip()

    # Parse slash command
    if raw.startswith("/"):
        parts = raw[1:].split(None, 1)
        skill    = parts[0].lower()
        question = parts[1].strip() if len(parts) > 1 else ""
    else:
        skill    = "research"   # default
        question = raw

    # /help — no pipeline needed
    if skill == "help" or not question:
        skills_list = "\n".join(f"  /{k}  — {v}" for k, v in SKILLS.items())
        return {
            "skill"      : "help",
            "question"   : "",
            "is_pipeline": False,
            "response"   : f"Available skills:\n{skills_list}",
        }

    # /memory — direct vector search, no pipeline
    if skill == "memory":
        raw_results = memory_retrieve(question, n_results=5)
        parsed      = json.loads(raw_results)
        results     = parsed.get("results", [])
        if not results:
            response = "No memory yet. Ask some questions first!"
        else:
            lines = [f"Top {len(results)} match(es) for '{question}':"]
            for i, r in enumerate(results, 1):
                preview = r["content"].split("\n")[0][:80]
                lines.append(f"  [{i}] (sim={r['similarity']}) {preview}")
            response = "\n".join(lines)
        return {
            "skill"      : "memory",
            "question"   : question,
            "is_pipeline": False,
            "response"   : response,
        }

    # All other skills go through the full pipeline
    if skill not in SKILLS:
        skill = "research"

    return {
        "skill"      : skill,
        "question"   : question,
        "is_pipeline": True,
        "response"   : None,
    }
