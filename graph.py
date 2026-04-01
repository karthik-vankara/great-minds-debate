import os
from dotenv import load_dotenv
load_dotenv()  # must run before any ChatOpenAI imports initialise

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from core.prompting import build_recent_chat_context
from state import DebateState
from personas import PERSONAS
from router import route_node
from tools import DEBATE_TOOLS

_debate_model = os.getenv("DEBATE_MODEL", "gpt-4.1")
_agent_llm = ChatOpenAI(model=_debate_model, temperature=0.5)
_tool_llm = ChatOpenAI(model=_debate_model, temperature=0.5).bind_tools(DEBATE_TOOLS)
_synthesis_llm = ChatOpenAI(model=_debate_model, temperature=0.3)


def _active_personas(state: DebateState) -> dict[str, dict]:
    return state.get("available_personas") or PERSONAS


def _agent_invoke_from_state(state: DebateState, agent_key: str, prompt: str) -> str:
    persona = _active_personas(state)[agent_key]
    response = _agent_llm.invoke([
        {"role": "system", "content": persona["system_prompt"]},
        {"role": "user", "content": prompt},
    ])
    return response.content.strip()


def _agent_invoke_with_tools(
    state: DebateState, agent_key: str, prompt: str, max_tool_calls: int = 3
) -> tuple[str, list[dict]]:
    """ReAct-style agent loop: LLM can call tools, get results, and respond.

    Returns (final_text, tool_records) where tool_records is a list of
    {tool, query, result} dicts for display in the UI.
    """
    persona = _active_personas(state)[agent_key]
    messages = [
        {"role": "system", "content": persona["system_prompt"]},
        {"role": "user", "content": prompt},
    ]
    tool_map = {t.name: t for t in DEBATE_TOOLS}
    tool_records: list[dict] = []

    for _ in range(max_tool_calls + 1):  # +1 for the final text response
        response = _tool_llm.invoke(messages)
        if not response.tool_calls:
            return response.content.strip(), tool_records
        # Process each tool call
        messages.append(response)
        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn is None:
                result = f"Unknown tool: {tc['name']}"
            else:
                result = tool_fn.invoke(tc["args"])
            print(f"  🔧 [{agent_key}] {tc['name']}({tc['args']}) → {str(result)[:120]}")
            tool_records.append({
                "tool": tc["name"],
                "query": tc["args"],
                "result": result,
            })
            messages.append({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tc["id"],
            })

    # Exhausted loop — force a final answer without tools
    response = _agent_llm.invoke(messages)
    return response.content.strip(), tool_records


def _context_block(state: DebateState) -> str:
    context = build_recent_chat_context(state.get("chat_history"))
    return "" if not context else f"{context}\n\n"


# ---------------------------------------------------------------------------
# Debate nodes
# ---------------------------------------------------------------------------

def agent_1_opening_node(state: DebateState) -> dict:
    context = _context_block(state)
    prompt = (
        f"{context}The topic for debate is:\n\n\"{state['user_input']}\"\n\n"
        "Give your opening statement on this topic. Be direct and take a clear stance."
        " You may use tools to research facts before forming your argument."
    )
    if state.get("use_tools", True):
        text, records = _agent_invoke_with_tools(state, state["agent_1"], prompt)
        for r in records:
            r["node"] = "agent_1_opening"
        return {"agent_1_opening": text, "tools_used": records}
    return {"agent_1_opening": _agent_invoke_from_state(state, state["agent_1"], prompt)}


def agent_2_opening_node(state: DebateState) -> dict:
    context = _context_block(state)
    prompt = (
        f"{context}The topic for debate is:\n\n\"{state['user_input']}\"\n\n"
        "Give your opening statement on this topic. Be direct and take a clear stance."
        " You may use tools to research facts before forming your argument."
    )
    if state.get("use_tools", True):
        text, records = _agent_invoke_with_tools(state, state["agent_2"], prompt)
        for r in records:
            r["node"] = "agent_2_opening"
        return {"agent_2_opening": text, "tools_used": records}
    return {"agent_2_opening": _agent_invoke_from_state(state, state["agent_2"], prompt)}


def human_review_node(state: DebateState) -> dict:
    """Pause execution and wait for human input before continuing."""
    interrupt({
        "agent_1_opening": state.get("agent_1_opening", ""),
        "agent_2_opening": state.get("agent_2_opening", ""),
        "agent_1": state.get("agent_1", ""),
        "agent_2": state.get("agent_2", ""),
        "message": "Review the opening statements. Continue, redirect, or skip to synthesis.",
    })
    return {}


def _human_review_router(state: DebateState) -> list[str]:
    """After human review, decide whether to skip to synthesis or continue."""
    if state.get("skip_to_synthesis"):
        return ["synthesis"]
    return ["agent_1_rebuttal", "agent_2_rebuttal"]


def _feedback_block(state: DebateState) -> str:
    feedback = state.get("human_feedback", "")
    if not feedback:
        return ""
    return (
        f"\n\nThe audience has provided this feedback: \"{feedback}\"\n"
        "Address this feedback in your rebuttal."
    )


def agent_1_rebuttal_node(state: DebateState) -> dict:
    active_personas = _active_personas(state)
    opponent = active_personas[state["agent_2"]]["display_name"]
    context = _context_block(state)
    feedback = _feedback_block(state)
    prompt = (
        f"{context}Topic: \"{state['user_input']}\"\n\n"
        f"{opponent} just said:\n\"{state['agent_2_opening']}\"\n\n"
        "Deliver your rebuttal. Challenge their key points directly and defend your position."
        " You may use tools to research counter-arguments."
        f"{feedback}"
    )
    if state.get("use_tools", True):
        text, records = _agent_invoke_with_tools(state, state["agent_1"], prompt)
        for r in records:
            r["node"] = "agent_1_rebuttal"
        return {"agent_1_rebuttal": text, "tools_used": records}
    return {"agent_1_rebuttal": _agent_invoke_from_state(state, state["agent_1"], prompt)}


def agent_2_rebuttal_node(state: DebateState) -> dict:
    active_personas = _active_personas(state)
    opponent = active_personas[state["agent_1"]]["display_name"]
    context = _context_block(state)
    feedback = _feedback_block(state)
    prompt = (
        f"{context}Topic: \"{state['user_input']}\"\n\n"
        f"{opponent} just said:\n\"{state['agent_1_opening']}\"\n\n"
        "Deliver your rebuttal. Challenge their key points directly and defend your position."
        " You may use tools to research counter-arguments."
        f"{feedback}"
    )
    if state.get("use_tools", True):
        text, records = _agent_invoke_with_tools(state, state["agent_2"], prompt)
        for r in records:
            r["node"] = "agent_2_rebuttal"
        return {"agent_2_rebuttal": text, "tools_used": records}
    return {"agent_2_rebuttal": _agent_invoke_from_state(state, state["agent_2"], prompt)}


def agent_1_closing_node(state: DebateState) -> dict:
    active_personas = _active_personas(state)
    opponent = active_personas[state["agent_2"]]["display_name"]
    context = _context_block(state)
    prompt = (
        f"{context}Topic: \"{state['user_input']}\"\n\n"
        f"The debate so far:\n"
        f"Your opening: \"{state['agent_1_opening']}\"\n"
        f"{opponent}'s rebuttal: \"{state['agent_2_rebuttal']}\"\n\n"
        "Give your closing argument. Summarize your core position and deliver a memorable final statement."
    )
    return {"agent_1_closing": _agent_invoke_from_state(state, state["agent_1"], prompt)}


def agent_2_closing_node(state: DebateState) -> dict:
    active_personas = _active_personas(state)
    opponent = active_personas[state["agent_1"]]["display_name"]
    context = _context_block(state)
    prompt = (
        f"{context}Topic: \"{state['user_input']}\"\n\n"
        f"The debate so far:\n"
        f"Your opening: \"{state['agent_2_opening']}\"\n"
        f"{opponent}'s rebuttal: \"{state['agent_1_rebuttal']}\"\n\n"
        "Give your closing argument. Summarize your core position and deliver a memorable final statement."
    )
    return {"agent_2_closing": _agent_invoke_from_state(state, state["agent_2"], prompt)}


def synthesis_node(state: DebateState) -> dict:
    active_personas = _active_personas(state)
    a1 = active_personas[state["agent_1"]]["display_name"]
    a2 = active_personas[state["agent_2"]]["display_name"]
    context = _context_block(state)
    prompt = (
        f"You are a neutral debate moderator. Summarize the following debate on the topic:\n"
        f"{context}"
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

checkpointer = MemorySaver()


def build_graph():
    builder = StateGraph(DebateState)

    builder.add_node("route", route_node)
    builder.add_node("agent_1_opening", agent_1_opening_node)
    builder.add_node("agent_2_opening", agent_2_opening_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("agent_1_rebuttal", agent_1_rebuttal_node)
    builder.add_node("agent_2_rebuttal", agent_2_rebuttal_node)
    builder.add_node("agent_1_closing", agent_1_closing_node)
    builder.add_node("agent_2_closing", agent_2_closing_node)
    builder.add_node("synthesis", synthesis_node)

    builder.add_edge(START, "route")
    builder.add_edge("route", "agent_1_opening")
    builder.add_edge("route", "agent_2_opening")
    builder.add_edge("agent_1_opening", "human_review")
    builder.add_edge("agent_2_opening", "human_review")
    builder.add_conditional_edges("human_review", _human_review_router)
    builder.add_edge("agent_1_rebuttal", "agent_1_closing")
    builder.add_edge("agent_2_rebuttal", "agent_2_closing")
    builder.add_edge("agent_1_closing", "synthesis")
    builder.add_edge("agent_2_closing", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile(checkpointer=checkpointer)


app = build_graph()
