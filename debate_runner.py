from rich.panel import Panel
from rich.rule import Rule

from graph import app
from state import DebateState


ROUND_HEADERS = {
    "agent_1_opening": ("round1", "[bold]Round 1 — Opening Statements[/bold]"),
    "agent_2_opening": ("round1", "[bold]Round 1 — Opening Statements[/bold]"),
    "agent_1_rebuttal": ("round2", "[bold]Round 2 — Rebuttals[/bold]"),
    "agent_2_rebuttal": ("round2", "[bold]Round 2 — Rebuttals[/bold]"),
    "agent_1_closing": ("round3", "[bold]Round 3 — Closing Arguments[/bold]"),
    "agent_2_closing": ("round3", "[bold]Round 3 — Closing Arguments[/bold]"),
}


NODE_LABELS = {
    "route": "🔍 Routing to best agents...",
    "agent_1_opening": "💬 Waiting for opening statement...",
    "agent_2_opening": "💬 Waiting for opening statement...",
    "agent_1_rebuttal": "⚔️  Preparing rebuttal...",
    "agent_2_rebuttal": "⚔️  Preparing rebuttal...",
    "agent_1_closing": "🎤 Preparing closing argument...",
    "agent_2_closing": "🎤 Preparing closing argument...",
    "synthesis": "🧠 Synthesizing debate...",
}


NEXT_NODES = {
    "route": "agent_1_opening",
    "agent_1_opening": "agent_2_opening",
    "agent_2_opening": "agent_1_rebuttal",
    "agent_1_rebuttal": "agent_2_rebuttal",
    "agent_2_rebuttal": "agent_1_closing",
    "agent_1_closing": "agent_2_closing",
    "agent_2_closing": "synthesis",
}


def print_agent_panel(console, agent_key: str, round_name: str, content: str, persona_pool: dict[str, dict]) -> None:
    persona = persona_pool[agent_key]
    color = persona["color"]
    title = f"[{color}]{persona['display_name']}[/{color}] — {round_name.upper()}"
    console.print(Panel(content, title=title, border_style=color.split()[-1]))


def print_routing_header(console, state: dict, persona_pool: dict[str, dict]) -> None:
    a1_name = persona_pool[state["agent_1"]]["display_name"]
    a2_name = persona_pool[state["agent_2"]]["display_name"]
    a1_pct = int(state["agent_1_confidence"] * 100)
    a2_pct = int(state["agent_2_confidence"] * 100)

    content = (
        f"[bold]Agent 1:[/bold] {a1_name} ({a1_pct}%)\n"
        f"[bold]Agent 2:[/bold] {a2_name} ({a2_pct}%)\n"
        f"[bold]Reason:[/bold] {state['routing_reason']}"
    )
    console.print(Panel(content, title="[bold white]🎯 ROUTER[/bold white]", border_style="white"))


def run_debate(console, user_input: str, chat_history: list, persona_pool: dict[str, dict], selection_mode: str = "auto", selected_agents: list[str] | None = None) -> list:
    initial_state: DebateState = {
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

    printed_headers: set[str] = set()
    result: dict = {}

    console.print(Rule("[dim]Debate starting...[/dim]"))

    with console.status("", spinner="dots") as status:
        status.update(f"[dim]{NODE_LABELS['route']}[/dim]")

        for event in app.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                result.update(node_output)
                status.stop()

                if node_name == "route":
                    print_routing_header(console, result, persona_pool)
                elif node_name in ROUND_HEADERS:
                    round_key, round_label = ROUND_HEADERS[node_name]
                    if round_key not in printed_headers:
                        console.print(Rule(round_label))
                        printed_headers.add(round_key)

                    agent_slot, round_name = node_name.rsplit("_", 1)
                    agent_key = result.get(agent_slot)
                    if agent_key:
                        print_agent_panel(console, agent_key, round_name, node_output[node_name], persona_pool)
                elif node_name == "synthesis":
                    console.print(Rule("[bold green]Synthesis[/bold green]"))
                    console.print(Panel(
                        node_output["synthesis"],
                        title="[bold green]🧠 MODERATOR SYNTHESIS[/bold green]",
                        border_style="green",
                    ))

                next_node = NEXT_NODES.get(node_name)
                if next_node:
                    status.update(f"[dim]{NODE_LABELS[next_node]}[/dim]")
                    status.start()

    return list(chat_history) + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": result.get("synthesis", "")},
    ]
