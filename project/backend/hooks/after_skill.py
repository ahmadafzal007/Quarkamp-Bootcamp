"""
after_skill hook — runs after the pipeline completes.
Responsibilities: log result, track cost via AgentOps, update metrics.
"""

import os
import logging
import datetime

logger = logging.getLogger("hooks.after_skill")


def after_skill(result: dict, skill: str, duration_s: float) -> None:
    """
    Called by the FastAPI route after the pipeline finishes.
    result: the AssignmentState returned by run_pipeline()
    """
    score    = result.get("quality_score", 0)
    revs     = result.get("revision_count", 0)
    session  = result.get("session_id", "?")
    log_len  = len(result.get("agent_log", []))

    logger.info(
        "Skill complete | skill=%s | session=%s | score=%d | revisions=%d | "
        "agents=%d | duration=%.2fs | ts=%s",
        skill, session, score, revs, log_len, duration_s,
        datetime.datetime.now().isoformat(),
    )

    # AgentOps tracking (only if key is set)
    agentops_key = os.getenv("AGENTOPS_API_KEY", "")
    if agentops_key:
        try:
            import agentops
            agentops.record(agentops.ActionEvent(
                action_type="skill_complete",
                params={
                    "skill"       : skill,
                    "score"       : score,
                    "revisions"   : revs,
                    "duration_s"  : round(duration_s, 2),
                    "session_id"  : session,
                },
                returns={"final_answer_len": len(result.get("final_answer", ""))},
            ))
        except Exception as e:
            logger.debug("AgentOps record failed: %s", e)
