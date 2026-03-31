from typing import Iterator

from graph import app
from state import DebateState


def build_initial_state(
    user_input: str,
    chat_history: list,
    persona_pool: dict[str, dict],
    selection_mode: str = "auto",
    selected_agents: list[str] | None = None,
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
) -> Iterator[tuple[str, dict, dict]]:
    initial_state = build_initial_state(
        user_input,
        chat_history,
        persona_pool,
        selection_mode=selection_mode,
        selected_agents=selected_agents,
    )

    result: dict = {}
    for event in app.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in event.items():
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
) -> dict:
    events: list[dict] = []
    last_result: dict = {}

    for node_name, node_output, result in stream_debate_updates(
        user_input,
        chat_history,
        persona_pool,
        selection_mode=selection_mode,
        selected_agents=selected_agents,
    ):
        events.append({"node": node_name, "output": node_output})
        last_result = result

    synthesis = last_result.get("synthesis", "")
    return {
        "events": events,
        "result": last_result,
        "chat_history": finalize_chat_history(chat_history, user_input, synthesis),
    }
