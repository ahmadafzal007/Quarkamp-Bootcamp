"""
CONCEPT 3 — AgentOps Monitoring
==================================
AgentOps traces every LLM call, tool call, and agent event.
It shows cost, latency, token usage, and errors in a live dashboard.

This script shows how to add AgentOps to the existing agent pipeline.

Setup:
  1. Sign up at https://agentops.ai (free)
  2. Get your API key
  3. Add AGENTOPS_API_KEY to .env

Run:
    conda run -n bootcamp python day5/concepts/03_agentops_monitoring.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"

AGENTOPS_KEY = os.getenv("AGENTOPS_API_KEY", "")


def demo_with_agentops():
    """Run a simple agent pipeline with AgentOps tracing."""
    if not AGENTOPS_KEY:
        print("\n  AGENTOPS_API_KEY not set — showing code structure only.")
        print("  Sign up at agentops.ai and add your key to .env\n")
        show_code_pattern()
        return

    try:
        import agentops
        agentops.init(AGENTOPS_KEY)
        print("\n  AgentOps initialized. Dashboard: https://app.agentops.ai\n")
    except ImportError:
        print("  agentops not installed: pip install agentops")
        return

    print("  Running traced agent pipeline...")

    # Every anthropic call is automatically traced when AgentOps is initialized
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="You are a helpful assistant.",
        messages=[{"role": "user", "content": "What are the key causes of the French Revolution?"}],
    )
    print(f"  Answer: {response.content[0].text[:100]}...")
    print(f"  Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
    print("\n  Check your AgentOps dashboard for the trace.")

    agentops.end_session("Success")


def show_code_pattern():
    """Explain the integration pattern without running it."""
    print("""
  AgentOps Integration Pattern
  ════════════════════════════

  1. Initialize once at startup:
     import agentops
     agentops.init(os.getenv("AGENTOPS_API_KEY"))

  2. Wrap agent runs in a session:
     @agentops.track_agent(name="Orchestrator")
     def orchestrator_node(state):
         ...

  3. Log custom events:
     agentops.record(agentops.ActionEvent(
         action_type="skill_invoked",
         params={"skill": "/research", "question": question},
     ))

  4. End the session:
     agentops.end_session("Success")  # or "Fail"

  What you see in the dashboard:
  ┌─────────────────────────────────────────────────────┐
  │  Session: 2025-05-01 14:32:11                       │
  │  Duration: 4.2s  |  Cost: $0.0012  |  Tokens: 1842  │
  │                                                     │
  │  [Orchestrator] 0.1s  route=research               │
  │  [Planner]      0.4s  subtasks=3                   │
  │  [Researcher]   1.8s  tool_calls=2                 │
  │    └─ web_search: "quantum entanglement" 0.6s      │
  │    └─ calculator: "6.626e-34 * 3e8 / 500e-9" 0s   │
  │  [Writer]       1.2s                               │
  │  [Critic]       0.7s  score=8/10                  │
  └─────────────────────────────────────────────────────┘

  In the project (project/backend/hooks/after_skill.py):
    - Every skill run is one AgentOps session
    - Every agent node is a tracked event
    - Cost is computed per session and stored in ChromaDB metadata
""")


def show_metrics_we_track():
    print("""
  Metrics tracked in production:
  ───────────────────────────────────────────────────────
  Per session:
    total_cost_usd, total_tokens, duration_seconds,
    skill_name, quality_score, revision_count

  Per agent node:
    agent_name, model_used, input_tokens, output_tokens,
    latency_ms, tool_calls (count and names)

  Alerts we set up:
    - cost_per_session > $0.10 → investigate prompt length
    - error_rate > 5%          → check tool failures
    - quality_score_avg < 7    → review Critic threshold
""")


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  AGENTOPS MONITORING")
    print("=" * 62)
    demo_with_agentops()
    show_metrics_we_track()
