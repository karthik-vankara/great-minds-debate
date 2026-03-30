import os
from dotenv import load_dotenv
load_dotenv()  # must run before any ChatOpenAI imports initialise

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from state import DebateState
from personas import PERSONAS
from router import route_node

_debate_model = os.getenv("DEBATE_MODEL", "gpt-4.1")
_agent_llm = ChatOpenAI(model=_debate_model, temperature=0.5)
_synthesis_llm = ChatOpenAI(model=_debate_model, temperature=0.3)


# ---------------------------------------------------------------------------
# Helper: invoke a persona with a prompt
# ---------------------------------------------------------------------------

def _agent_invoke(agent_key: str, prompt: str) -> str:
    persona = PERSONAS[agent_key]
    response = _agent_llm.invoke([
        {"role": "system", "content": persona["system_prompt"]},
        {"role": "user", "content": prompt},
    ])
    return response.content.strip()


# ---------------------------------------------------------------------------
# Debate nodes
# ---------------------------------------------------------------------------

def agent_1_opening_node(state: DebateState) -> dict:
    prompt = (
        f"The topic for debate is:\n\n\"{state['user_input']}\"\n\n"
        "Give your opening statement on this topic. Be direct and take a clear stance."
    )
    return {"agent_1_opening": _agent_invoke(state["agent_1"], prompt)}


def agent_2_opening_node(state: DebateState) -> dict:
    prompt = (
        f"The topic for debate is:\n\n\"{state['user_input']}\"\n\n"
        "Give your opening statement on this topic. Be direct and take a clear stance."
    )
    return {"agent_2_opening": _agent_invoke(state["agent_2"], prompt)}


def agent_1_rebuttal_node(state: DebateState) -> dict:
    opponent = PERSONAS[state["agent_2"]]["display_name"]
    prompt = (
        f"Topic: \"{state['user_input']}\"\n\n"
        f"{opponent} just said:\n\"{state['agent_2_opening']}\"\n\n"
        "Deliver your rebuttal. Challenge their key points directly and defend your position."
    )
    return {"agent_1_rebuttal": _agent_invoke(state["agent_1"], prompt)}


def agent_2_rebuttal_node(state: DebateState) -> dict:
    opponent = PERSONAS[state["agent_1"]]["display_name"]
    prompt = (
        f"Topic: \"{state['user_input']}\"\n\n"
        f"{opponent} just said:\n\"{state['agent_1_opening']}\"\n\n"
        "Deliver your rebuttal. Challenge their key points directly and defend your position."
    )
    return {"agent_2_rebuttal": _agent_invoke(state["agent_2"], prompt)}


def agent_1_closing_node(state: DebateState) -> dict:
    opponent = PERSONAS[state["agent_2"]]["display_name"]
    prompt = (
        f"Topic: \"{state['user_input']}\"\n\n"
        f"The debate so far:\n"
        f"Your opening: \"{state['agent_1_opening']}\"\n"
        f"{opponent}'s rebuttal: \"{state['agent_2_rebuttal']}\"\n\n"
        "Give your closing argument. Summarize your core position and deliver a memorable final statement."
    )
    return {"agent_1_closing": _agent_invoke(state["agent_1"], prompt)}


def agent_2_closing_node(state: DebateState) -> dict:
    opponent = PERSONAS[state["agent_1"]]["display_name"]
    prompt = (
        f"Topic: \"{state['user_input']}\"\n\n"
        f"The debate so far:\n"
        f"Your opening: \"{state['agent_2_opening']}\"\n"
        f"{opponent}'s rebuttal: \"{state['agent_1_rebuttal']}\"\n\n"
        "Give your closing argument. Summarize your core position and deliver a memorable final statement."
    )
    return {"agent_2_closing": _agent_invoke(state["agent_2"], prompt)}


def synthesis_node(state: DebateState) -> dict:
    a1 = PERSONAS[state["agent_1"]]["display_name"]
    a2 = PERSONAS[state["agent_2"]]["display_name"]
    prompt = (
        f"You are a neutral debate moderator. Summarize the following debate on the topic:\n"
        f"\"{state['user_input']}\"\n\n"
        f"--- {a1} ---\n"
        f"Opening: {state['agent_1_opening']}\n"
        f"Rebuttal: {state['agent_1_rebuttal']}\n"
        f"Closing: {state['agent_1_closing']}\n\n"
        f"--- {a2} ---\n"
        f"Opening: {state['agent_2_opening']}\n"
        f"Rebuttal: {state['agent_2_rebuttal']}\n"
        f"Closing: {state['agent_2_closing']}\n\n"
        "Provide a concise synthesis: key points of agreement, points of disagreement, "
        "and what someone should take away from this debate. 3-5 sentences."
    )
    response = _synthesis_llm.invoke([
        {"role": "system", "content": "You are a sharp, neutral debate moderator."},
        {"role": "user", "content": prompt},
    ])
    return {"synthesis": response.content.strip()}


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph():
    builder = StateGraph(DebateState)

    builder.add_node("route", route_node)
    builder.add_node("agent_1_opening", agent_1_opening_node)
    builder.add_node("agent_2_opening", agent_2_opening_node)
    builder.add_node("agent_1_rebuttal", agent_1_rebuttal_node)
    builder.add_node("agent_2_rebuttal", agent_2_rebuttal_node)
    builder.add_node("agent_1_closing", agent_1_closing_node)
    builder.add_node("agent_2_closing", agent_2_closing_node)
    builder.add_node("synthesis", synthesis_node)

    builder.add_edge(START, "route")
    builder.add_edge("route", "agent_1_opening")
    builder.add_edge("route", "agent_2_opening")
    builder.add_edge("agent_1_opening", "agent_1_rebuttal")
    builder.add_edge("agent_2_opening", "agent_2_rebuttal")
    builder.add_edge("agent_1_rebuttal", "agent_1_closing")
    builder.add_edge("agent_2_rebuttal", "agent_2_closing")
    builder.add_edge("agent_1_closing", "synthesis")
    builder.add_edge("agent_2_closing", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile()


app = build_graph()
