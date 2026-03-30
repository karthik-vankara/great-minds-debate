from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class DebateState(TypedDict):
    user_input: str
    chat_history: Annotated[list, add_messages]

    # Router output
    agent_1: str
    agent_2: str
    agent_1_confidence: float
    agent_2_confidence: float
    routing_reason: str

    # Debate rounds
    agent_1_opening: str
    agent_2_opening: str
    agent_1_rebuttal: str
    agent_2_rebuttal: str
    agent_1_closing: str
    agent_2_closing: str

    # Final synthesis
    synthesis: str
