import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from personas import PERSONAS, AGENT_KEYS
from state import DebateState

load_dotenv()


class RouterOutput(BaseModel):
    agent_1: str = Field(description="Key of the first most relevant agent")
    agent_2: str = Field(description="Key of the second most relevant agent")
    agent_1_confidence: float = Field(description="Confidence score 0.0-1.0 for agent_1")
    agent_2_confidence: float = Field(description="Confidence score 0.0-1.0 for agent_2")
    routing_reason: str = Field(description="One sentence explaining why these two agents were chosen")


_router_model = os.getenv("ROUTER_MODEL", "gpt-4o-mini")
_router_llm = ChatOpenAI(model=_router_model, temperature=0).with_structured_output(RouterOutput)

def _build_router_system(persona_pool: dict[str, dict], agent_keys: list[str]) -> str:
    agent_summary = "\n".join(
        f"- {key}: {data['display_name']} — expertise in: {', '.join(data['tags'][:6])}"
        for key, data in persona_pool.items()
    )

    return f"""You are a debate moderator. Given a user's question or idea, select the 2 most relevant agents to debate it.

Available agents:
{agent_summary}

Return valid agent keys only from: {agent_keys}.
Do NOT pick the same agent twice.
"""


def _fallback_pair(agent_keys: list[str]) -> tuple[str, str]:
    if len(agent_keys) < 2:
        raise ValueError("At least two personas are required for routing.")
    return agent_keys[0], agent_keys[1]


def route_node(state: DebateState) -> dict:
    persona_pool = state.get("available_personas") or PERSONAS
    active_keys = list(persona_pool.keys()) or AGENT_KEYS

    if state.get("selection_mode") == "manual":
        selected = state.get("selected_agents") or []
        if len(selected) == 2 and selected[0] in persona_pool and selected[1] in persona_pool and selected[0] != selected[1]:
            return {
                "agent_1": selected[0],
                "agent_2": selected[1],
                "agent_1_confidence": 1.0,
                "agent_2_confidence": 1.0,
                "routing_reason": "Manual selection mode.",
            }

    user_input = state["user_input"]
    router_system = _build_router_system(persona_pool, active_keys)
    result: RouterOutput = _router_llm.invoke([
        {"role": "system", "content": router_system},
        {"role": "user", "content": user_input},
    ])

    # Validate returned keys are real
    valid_keys = set(active_keys)
    if result.agent_1 not in valid_keys or result.agent_2 not in valid_keys or result.agent_1 == result.agent_2:
        result.agent_1, result.agent_2 = _fallback_pair(active_keys)
        result.routing_reason = "Fallback selection due to invalid router output."

    return {
        "agent_1": result.agent_1,
        "agent_2": result.agent_2,
        "agent_1_confidence": round(result.agent_1_confidence, 2),
        "agent_2_confidence": round(result.agent_2_confidence, 2),
        "routing_reason": result.routing_reason,
    }
