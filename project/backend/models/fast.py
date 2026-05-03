"""
fast model — claude-haiku-4-5
Use for: routing, classification, quick judgements, Critic scoring.
"""

import anthropic
from ..config import ANTHROPIC_API_KEY, MODEL_FAST

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def fast_model(system: str, user: str, max_tokens: int = 200) -> str:
    response = _client.messages.create(
        model=MODEL_FAST,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
