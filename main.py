from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from graph import app
from personas import PERSONAS
from state import DebateState

load_dotenv()

console = Console()

ROUND_COLORS = {
    "opening": "bold",
    "rebuttal": "italic",
    "closing": "bold italic",
}


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

    console.print(Rule("[dim]Running debate...[/dim]"))
    result = app.invoke(initial_state)

    # Print routing header
    print_routing_header(result)

    a1 = result["agent_1"]
    a2 = result["agent_2"]

    # Round 1 — Openings
    console.print(Rule("[bold]Round 1 — Opening Statements[/bold]"))
    print_agent_panel(a1, "opening", result["agent_1_opening"])
    print_agent_panel(a2, "opening", result["agent_2_opening"])

    # Round 2 — Rebuttals
    console.print(Rule("[bold]Round 2 — Rebuttals[/bold]"))
    print_agent_panel(a1, "rebuttal", result["agent_1_rebuttal"])
    print_agent_panel(a2, "rebuttal", result["agent_2_rebuttal"])

    # Round 3 — Closing Arguments
    console.print(Rule("[bold]Round 3 — Closing Arguments[/bold]"))
    print_agent_panel(a1, "closing", result["agent_1_closing"])
    print_agent_panel(a2, "closing", result["agent_2_closing"])

    # Synthesis
    console.print(Rule("[bold green]Synthesis[/bold green]"))
    console.print(Panel(result["synthesis"], title="[bold green]🧠 MODERATOR SYNTHESIS[/bold green]", border_style="green"))

    # Update chat history with this exchange
    updated_history = list(chat_history) + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": result["synthesis"]},
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
