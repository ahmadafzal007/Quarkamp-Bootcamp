"""
powerful model — claude-opus-4-7
Use for: complex reasoning, /powerful flag, hard assignments.
Only invoke when the user explicitly opts in — it's 15x more expensive.
"""

import anthropic
from ..config import ANTHROPIC_API_KEY, MODEL_POWERFUL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def powerful_model(system: str, user: str, max_tokens: int = 1200) -> str:
    response = _client.messages.create(
        model=MODEL_POWERFUL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
