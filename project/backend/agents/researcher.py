"""
Researcher Agent
Reads: question, subtasks, memory_context
Writes: research (dict), agent_log
Model: balanced + tools (plugins)
"""

from ..models.balanced import balanced_model_with_tools
from ..plugins import PLUGIN_SCHEMAS, execute_plugin


_SYSTEM = """You are a thorough research assistant.
For each subtask, use the available tools to gather accurate information.
Use web_search for current facts. Use memory_retrieve for past answers.
Be precise — 3-4 sentences per finding."""


def researcher_node(state: dict) -> dict:
    findings: dict[str, str] = {}
    tools_called: list[str]  = []

    memory_block = ""
    if state.get("memory_context"):
        memory_block = "\n\nContext from memory:\n" + "\n".join(
            f"  {c[:150]}" for c in state["memory_context"]
        )

    for subtask in state.get("subtasks", []):
        messages = [{
            "role"   : "user",
            "content": f"Subtask: {subtask}\nBroader question: {state['question']}{memory_block}",
        }]

        # ReAct loop for each subtask
        for _ in range(4):
            response = balanced_model_with_tools(
                system=_SYSTEM,
                messages=messages,
                tools=PLUGIN_SCHEMAS,
                max_tokens=500,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text = next((b.text for b in response.content if hasattr(b, "text")), "")
                findings[subtask] = text or "No findings for this subtask."
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tools_called.append(block.name)
                obs = execute_plugin(block.name, block.input)
                tool_results.append({
                    "type"       : "tool_result",
                    "tool_use_id": block.id,
                    "content"    : obs,
                })

            if not tool_results:
                # Model did not call any tools — extract any text and stop
                text = next((b.text for b in response.content if hasattr(b, "text")), "")
                findings[subtask] = text or "No relevant findings."
                break

            messages.append({"role": "user", "content": tool_results})
        else:
            # Fallback if loop exhausted
            findings[subtask] = "Could not gather sufficient information for this subtask."

    return {
        "research" : findings,
        "agent_log": state.get("agent_log", []) + [
            f"[Researcher] {len(findings)} findings, tools: {list(set(tools_called))}"
        ],
    }
