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


_router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(RouterOutput)

_AGENT_SUMMARY = "\n".join(
    f"- {key}: {data['display_name']} — expertise in: {', '.join(data['tags'][:6])}"
    for key, data in PERSONAS.items()
)

_ROUTER_SYSTEM = f"""You are a debate moderator. Given a user's question or idea, select the 2 most relevant agents to debate it.

Available agents:
{_AGENT_SUMMARY}

Return valid agent keys only from: {AGENT_KEYS}.
Do NOT pick the same agent twice.
"""


def route_node(state: DebateState) -> dict:
    user_input = state["user_input"]
    result: RouterOutput = _router_llm.invoke([
        {"role": "system", "content": _ROUTER_SYSTEM},
        {"role": "user", "content": user_input},
    ])

    # Validate returned keys are real
    valid_keys = set(AGENT_KEYS)
    if result.agent_1 not in valid_keys or result.agent_2 not in valid_keys:
        # Fallback: pick first two
        result.agent_1, result.agent_2 = AGENT_KEYS[0], AGENT_KEYS[1]
        result.routing_reason = "Fallback selection due to invalid router output."

    return {
        "agent_1": result.agent_1,
        "agent_2": result.agent_2,
        "agent_1_confidence": round(result.agent_1_confidence, 2),
        "agent_2_confidence": round(result.agent_2_confidence, 2),
        "routing_reason": result.routing_reason,
    }
