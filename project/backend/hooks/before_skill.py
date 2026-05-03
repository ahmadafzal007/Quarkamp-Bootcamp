"""
before_skill hook — runs before any skill pipeline starts.
Responsibilities: validate input, log request, check guardrails.
"""

import logging
import datetime

logger = logging.getLogger("hooks.before_skill")

BLOCKED_PATTERNS = [
    "ignore all previous",
    "ignore your instructions",
    "jailbreak",
    "dan mode",
]

MAX_QUESTION_LENGTH = 2000


def before_skill(question: str, skill: str) -> dict:
    """
    Returns {"ok": True} or {"ok": False, "reason": "..."}.
    Called by the FastAPI route before invoking the pipeline.
    """
    # Length check
    if len(question) > MAX_QUESTION_LENGTH:
        return {"ok": False, "reason": f"Question too long (max {MAX_QUESTION_LENGTH} chars)"}

    # Empty input
    if not question.strip():
        return {"ok": False, "reason": "Question cannot be empty"}

    # Prompt injection guardrail
    q_lower = question.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in q_lower:
            logger.warning("Blocked potential prompt injection: %s", question[:100])
            return {"ok": False, "reason": "Input contains disallowed patterns"}

    # Log the request
    logger.info(
        "Skill invoked | skill=%s | question_len=%d | ts=%s",
        skill, len(question), datetime.datetime.now().isoformat(),
    )

    return {"ok": True}
