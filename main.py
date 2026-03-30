from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from graph import app
from personas import PERSONAS
from state import DebateState

load_dotenv()

console = Console()


def print_agent_panel(agent_key: str, round_name: str, content: str) -> None:
    persona = PERSONAS[agent_key]
    color = persona["color"]
    title = f"[{color}]{persona['display_name']}[/{color}] — {round_name.upper()}"
    console.print(Panel(content, title=title, border_style=color.split()[-1]))


def print_routing_header(state: dict) -> None:
    a1_name = PERSONAS[state["agent_1"]]["display_name"]
    a2_name = PERSONAS[state["agent_2"]]["display_name"]
    a1_pct = int(state["agent_1_confidence"] * 100)
    a2_pct = int(state["agent_2_confidence"] * 100)

    content = (
        f"[bold]Agent 1:[/bold] {a1_name} ({a1_pct}%)\n"
        f"[bold]Agent 2:[/bold] {a2_name} ({a2_pct}%)\n"
        f"[bold]Reason:[/bold] {state['routing_reason']}"
    )
    console.print(Panel(content, title="[bold white]🎯 ROUTER[/bold white]", border_style="white"))


def run_debate(user_input: str, chat_history: list) -> list:
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
    }

    # Track which round headers have already been printed
    printed_headers: set[str] = set()
    # Accumulate full state so chat_history can be updated at the end
    result: dict = {}

    ROUND_HEADERS = {
        "agent_1_opening":  ("round1", "[bold]Round 1 — Opening Statements[/bold]"),
        "agent_2_opening":  ("round1", "[bold]Round 1 — Opening Statements[/bold]"),
        "agent_1_rebuttal": ("round2", "[bold]Round 2 — Rebuttals[/bold]"),
        "agent_2_rebuttal": ("round2", "[bold]Round 2 — Rebuttals[/bold]"),
        "agent_1_closing":  ("round3", "[bold]Round 3 — Closing Arguments[/bold]"),
        "agent_2_closing":  ("round3", "[bold]Round 3 — Closing Arguments[/bold]"),
    }

    NODE_LABELS = {
        "route":            "🔍 Routing to best agents...",
        "agent_1_opening":  "💬 Waiting for opening statement...",
        "agent_2_opening":  "💬 Waiting for opening statement...",
        "agent_1_rebuttal": "⚔️  Preparing rebuttal...",
        "agent_2_rebuttal": "⚔️  Preparing rebuttal...",
        "agent_1_closing":  "🎤 Preparing closing argument...",
        "agent_2_closing":  "🎤 Preparing closing argument...",
        "synthesis":        "🧠 Synthesizing debate...",
    }

    console.print(Rule("[dim]Debate starting...[/dim]"))

    with console.status("", spinner="dots") as status:
        # Show spinner label for first node before streaming begins
        status.update(f"[dim]{NODE_LABELS['route']}[/dim]")

        for event in app.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                # Merge into accumulated result
                result.update(node_output)

                # Stop spinner so panel prints cleanly
                status.stop()

                if node_name == "route":
                    # Routing done — print header immediately
                    print_routing_header(result)

                elif node_name in ROUND_HEADERS:
                    round_key, round_label = ROUND_HEADERS[node_name]
                    if round_key not in printed_headers:
                        console.print(Rule(round_label))
                        printed_headers.add(round_key)

                    # Determine which agent key and round name to display
                    agent_slot, round_name = node_name.rsplit("_", 1)  # e.g. agent_1, opening
                    agent_key = result.get(agent_slot)  # "steve_jobs", "elon_musk", etc.
                    if agent_key:
                        print_agent_panel(agent_key, round_name, node_output[node_name])

                elif node_name == "synthesis":
                    console.print(Rule("[bold green]Synthesis[/bold green]"))
                    console.print(Panel(
                        node_output["synthesis"],
                        title="[bold green]🧠 MODERATOR SYNTHESIS[/bold green]",
                        border_style="green",
                    ))

                # Determine next expected node label for the spinner
                next_nodes = {
                    "route":            "agent_1_opening",
                    "agent_1_opening":  "agent_2_opening",
                    "agent_2_opening":  "agent_1_rebuttal",
                    "agent_1_rebuttal": "agent_2_rebuttal",
                    "agent_2_rebuttal": "agent_1_closing",
                    "agent_1_closing":  "agent_2_closing",
                    "agent_2_closing":  "synthesis",
                }
                next_node = next_nodes.get(node_name)
                if next_node:
                    status.update(f"[dim]{NODE_LABELS[next_node]}[/dim]")
                    status.start()

    # Update chat history with this exchange
    updated_history = list(chat_history) + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": result.get("synthesis", "")},
    ]
    return updated_history


def main():
    console.print(Panel(
        "[bold]Welcome to the AI Persona Debate Arena![/bold]\n\n"
        "Ask any idea or question and watch [cyan]Steve Jobs[/cyan], [yellow]Elon Musk[/yellow], "
        "[green]Einstein[/green], and [blue]Zuckerberg[/blue] debate it.\n\n"
        "Type [bold red]quit[/bold red] or [bold red]exit[/bold red] to stop.",
        title="[bold magenta]🎤 DEBATE ARENA[/bold magenta]",
        border_style="magenta",
    ))

    chat_history: list = []

    while True:
        console.print()
        try:
            user_input = console.input("[bold magenta]You:[/bold magenta] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting...[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit"}:
            console.print("[bold]Goodbye! 👋[/bold]")
            break

        try:
            chat_history = run_debate(user_input, chat_history)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
