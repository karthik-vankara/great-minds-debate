import uuid
from typing import Iterator

from langgraph.types import Command

from graph import app
from state import DebateState


def build_initial_state(
    user_input: str,
    chat_history: list,
    persona_pool: dict[str, dict],
    selection_mode: str = "auto",
    selected_agents: list[str] | None = None,
    use_tools: bool = True,
) -> DebateState:
    return {
        "user_input": user_input,
        "chat_history": chat_history,
        "agent_1": "",
        "agent_2": "",
        "agent_1_confidence": 0.0,
        "agent_2_confidence": 0.0,
        "routing_reason": "",
        "agent_1_opening": "",
        "agent_2_opening": "",
        "agent_1_rebuttal": "",
        "agent_2_rebuttal": "",
        "agent_1_closing": "",
        "agent_2_closing": "",
        "synthesis": "",
        "human_feedback": "",
        "skip_to_synthesis": False,
        "tools_used": [],
        "use_tools": use_tools,
        "available_personas": persona_pool,
        "selection_mode": selection_mode,
        "selected_agents": selected_agents or [],
    }


def stream_debate_updates(
    user_input: str,
    chat_history: list,
    persona_pool: dict[str, dict],
    selection_mode: str = "auto",
    selected_agents: list[str] | None = None,
    use_tools: bool = True,
) -> Iterator[tuple[str, dict, dict]]:
    debate_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": debate_id}}

    initial_state = build_initial_state(
        user_input,
        chat_history,
        persona_pool,
        selection_mode=selection_mode,
        selected_agents=selected_agents,
        use_tools=use_tools,
    )

    result: dict = {}
    for event in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "__interrupt__":
                continue  # LangGraph internal interrupt marker — skip it
            # Merge tools_used lists instead of replacing
            if "tools_used" in node_output:
                print(f"  [stream] {node_name} has {len(node_output['tools_used'])} tool records")
            if "tools_used" in node_output and "tools_used" in result:
                result["tools_used"] = result["tools_used"] + node_output["tools_used"]
                rest = {k: v for k, v in node_output.items() if k != "tools_used"}
                result.update(rest)
            else:
                result.update(node_output)
            print(f"  [stream] result keys: {list(result.keys())}, tools_used count: {len(result.get('tools_used', []))}")
            yield node_name, node_output, dict(result)

    # Check if the graph was interrupted (paused at human_review)
    state_snapshot = app.get_state(config)
    if state_snapshot.next:
        # Graph is paused — emit interrupt marker with debate_id
        yield "__interrupt__", {"debate_id": debate_id}, dict(result)


def resume_debate_updates(
    debate_id: str,
    human_feedback: str = "",
    skip_to_synthesis: bool = False,
) -> Iterator[tuple[str, dict, dict]]:
    config = {"configurable": {"thread_id": debate_id}}

    # Inject human feedback into the paused graph state, then resume
    result: dict = {}

    # Get current accumulated state to seed result dict
    state_snapshot = app.get_state(config)
    if state_snapshot.values:
        for key in ("agent_1", "agent_2", "agent_1_confidence", "agent_2_confidence",
                     "routing_reason", "agent_1_opening", "agent_2_opening", "tools_used"):
            if key in state_snapshot.values:
                result[key] = state_snapshot.values[key]

    # Update state with human feedback before resuming
    app.update_state(
        config,
        {"human_feedback": human_feedback, "skip_to_synthesis": skip_to_synthesis},
        as_node="human_review",
    )

    for event in app.stream(
        Command(resume=True),
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            if node_name == "__interrupt__":
                continue
            # Merge tools_used lists instead of replacing
            if "tools_used" in node_output and "tools_used" in result:
                result["tools_used"] = result["tools_used"] + node_output["tools_used"]
                rest = {k: v for k, v in node_output.items() if k != "tools_used"}
                result.update(rest)
            else:
                result.update(node_output)
            yield node_name, node_output, dict(result)


def finalize_chat_history(chat_history: list, user_input: str, synthesis: str) -> list:
    return list(chat_history) + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": synthesis},
    ]


def run_debate_orchestration(
    user_input: str,
    chat_history: list,
    persona_pool: dict[str, dict],
    selection_mode: str = "auto",
    selected_agents: list[str] | None = None,
    use_tools: bool = True,
) -> dict:
    events: list[dict] = []
    last_result: dict = {}
    debate_id: str | None = None

    for node_name, node_output, result in stream_debate_updates(
        user_input,
        chat_history,
        persona_pool,
        selection_mode=selection_mode,
        selected_agents=selected_agents,
        use_tools=use_tools,
    ):
        if node_name == "__interrupt__":
            # Auto-resume with no feedback for sync endpoint
            debate_id = node_output["debate_id"]
            for rn, ro, rr in resume_debate_updates(debate_id):
                events.append({"node": rn, "output": ro})
                last_result = rr
        else:
            events.append({"node": node_name, "output": node_output})
            last_result = result

    synthesis = last_result.get("synthesis", "")
    return {
        "events": events,
        "result": last_result,
        "chat_history": finalize_chat_history(chat_history, user_input, synthesis),
    }
