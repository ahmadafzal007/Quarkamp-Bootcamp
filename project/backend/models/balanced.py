"""
balanced model — claude-sonnet-4-6
Use for: Planner, Researcher, Writer — the main reasoning workhorses.
"""

import anthropic
from ..config import ANTHROPIC_API_KEY, MODEL_BALANCED

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def balanced_model(system: str, user: str, max_tokens: int = 800) -> str:
    response = _client.messages.create(
        model=MODEL_BALANCED,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def balanced_model_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_tokens: int = 800,
):
    return _client.messages.create(
        model=MODEL_BALANCED,
        max_tokens=max_tokens,
        system=system,
        tools=tools,
        messages=messages,
    )
