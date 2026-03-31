from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from graph import app
from personas import (
    BUILTIN_PERSONAS,
    get_active_personas,
    refresh_personas,
    remove_custom_persona,
    save_custom_persona,
)
from session_store import SessionStore
from state import DebateState

load_dotenv()

console = Console()
session_store = SessionStore()


def print_agent_panel(agent_key: str, round_name: str, content: str, persona_pool: dict[str, dict]) -> None:
    persona = persona_pool[agent_key]
    color = persona["color"]
    title = f"[{color}]{persona['display_name']}[/{color}] — {round_name.upper()}"
    console.print(Panel(content, title=title, border_style=color.split()[-1]))


def print_routing_header(state: dict, persona_pool: dict[str, dict]) -> None:
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


def run_debate(user_input: str, chat_history: list, selection_mode: str = "auto", selected_agents: list[str] | None = None) -> list:
    active_personas = get_active_personas()
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
        "available_personas": active_personas,
        "selection_mode": selection_mode,
        "selected_agents": selected_agents or [],
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
                    print_routing_header(result, active_personas)

                elif node_name in ROUND_HEADERS:
                    round_key, round_label = ROUND_HEADERS[node_name]
                    if round_key not in printed_headers:
                        console.print(Rule(round_label))
                        printed_headers.add(round_key)

                    # Determine which agent key and round name to display
                    agent_slot, round_name = node_name.rsplit("_", 1)  # e.g. agent_1, opening
                    agent_key = result.get(agent_slot)  # "steve_jobs", "elon_musk", etc.
                    if agent_key:
                        print_agent_panel(agent_key, round_name, node_output[node_name], active_personas)

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
        "Commands: [bold]/personas[/bold], [bold]/sessions[/bold], [bold]/mode[/bold], [bold]/help[/bold].\n"
        "Type [bold red]quit[/bold red] or [bold red]exit[/bold red] to stop.",
        title="[bold magenta]🎤 DEBATE ARENA[/bold magenta]",
        border_style="magenta",
    ))

    chat_history: list = []
    selection_mode = "auto"
    current_session_name: str | None = None

    def print_help() -> None:
        console.print(Panel(
            "[bold]/personas[/bold] Manage personas (list/add/edit/delete)\n"
            "[bold]/sessions[/bold] Manage chat sessions (list/save/load/delete)\n"
            "[bold]/mode[/bold] Switch between auto and manual selection\n"
            "[bold]/help[/bold] Show this help",
            title="[bold white]Commands[/bold white]",
            border_style="white",
        ))

    def manage_sessions() -> tuple[list, str, str | None]:
        nonlocal chat_history, selection_mode, current_session_name
        while True:
            console.print("\n[bold]Session Manager[/bold] - choose: list, save, load, delete, back")
            action = console.input("session> ").strip().lower()
            if action == "back":
                return chat_history, selection_mode, current_session_name

            if action == "list":
                sessions = session_store.list_sessions()
                if not sessions:
                    console.print("[yellow]No saved sessions found.[/yellow]")
                    continue
                lines = [
                    f"[bold]{item['name']}[/bold] | mode={item['selection_mode']} | messages={item['messages']} | updated={item['updated_at']}"
                    for item in sessions
                ]
                console.print(Panel("\n".join(lines), title="[bold white]Saved Sessions[/bold white]", border_style="white"))
                continue

            if action == "save":
                default_name = current_session_name or datetime.now().strftime("session_%Y%m%d_%H%M%S")
                name = console.input(f"Session name [{default_name}]: ").strip() or default_name
                try:
                    saved_name = session_store.save_session(name, chat_history, selection_mode)
                    current_session_name = saved_name
                    console.print(f"[green]Session saved:[/green] {saved_name}")
                except Exception as exc:
                    console.print(f"[bold red]Failed to save session:[/bold red] {exc}")
                continue

            if action == "load":
                name = console.input("Session name to load: ").strip()
                if not name:
                    console.print("[yellow]Session name is required.[/yellow]")
                    continue
                try:
                    loaded = session_store.load_session(name)
                    chat_history = loaded["chat_history"]
                    selection_mode = loaded["selection_mode"]
                    current_session_name = loaded["name"]
                    console.print(
                        f"[green]Loaded session:[/green] {current_session_name} "
                        f"(messages={len(chat_history)}, mode={selection_mode})"
                    )
                except Exception as exc:
                    console.print(f"[bold red]Failed to load session:[/bold red] {exc}")
                continue

            if action == "delete":
                name = console.input("Session name to delete: ").strip()
                if not name:
                    console.print("[yellow]Session name is required.[/yellow]")
                    continue
                try:
                    deleted = session_store.delete_session(name)
                    if deleted:
                        if current_session_name == name:
                            current_session_name = None
                        console.print(f"[green]Deleted session:[/green] {name}")
                    else:
                        console.print("[yellow]Session not found.[/yellow]")
                except Exception as exc:
                    console.print(f"[bold red]Failed to delete session:[/bold red] {exc}")
                continue

            console.print("[yellow]Unknown action. Use list, save, load, delete, or back.[/yellow]")

    def list_personas() -> None:
        active = get_active_personas()
        lines = []
        for key, data in active.items():
            origin = "built-in" if key in BUILTIN_PERSONAS else "custom"
            lines.append(f"[bold]{key}[/bold] ({origin}) - {data['display_name']}")
        console.print(Panel("\n".join(lines), title="[bold white]Personas[/bold white]", border_style="white"))

    def prompt_persona_payload(existing: dict | None = None) -> dict:
        existing = existing or {}
        display_name = console.input(f"Display name [{existing.get('display_name', '')}]: ").strip() or existing.get("display_name", "")
        color = console.input(f"Color [{existing.get('color', 'bold white')}]: ").strip() or existing.get("color", "bold white")
        tags_input = console.input(
            f"Tags comma-separated [{', '.join(existing.get('tags', []))}]: "
        ).strip()
        system_prompt = console.input("System prompt: ").strip() or existing.get("system_prompt", "")
        tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()] if tags_input else existing.get("tags", [])
        return {
            "display_name": display_name,
            "color": color,
            "tags": tags,
            "system_prompt": system_prompt,
        }

    def manage_personas() -> None:
        while True:
            console.print("\n[bold]Persona Manager[/bold] - choose: list, add, edit, delete, back")
            action = console.input("persona> ").strip().lower()
            if action == "back":
                return
            if action == "list":
                list_personas()
                continue
            if action == "add":
                key = console.input("New persona key (snake_case): ").strip().lower()
                if not key:
                    console.print("[yellow]Persona key is required.[/yellow]")
                    continue
                payload = prompt_persona_payload()
                try:
                    save_custom_persona(key, payload)
                    console.print(f"[green]Saved custom persona:[/green] {key}")
                except Exception as exc:
                    console.print(f"[bold red]Failed to save persona:[/bold red] {exc}")
                continue
            if action == "edit":
                key = console.input("Persona key to edit: ").strip().lower()
                active = get_active_personas()
                if key in BUILTIN_PERSONAS:
                    console.print("[yellow]Built-in personas are immutable. Create a new custom key instead.[/yellow]")
                    continue
                if key not in active:
                    console.print("[yellow]Persona not found.[/yellow]")
                    continue
                payload = prompt_persona_payload(active[key])
                try:
                    save_custom_persona(key, payload)
                    console.print(f"[green]Updated custom persona:[/green] {key}")
                except Exception as exc:
                    console.print(f"[bold red]Failed to update persona:[/bold red] {exc}")
                continue
            if action == "delete":
                key = console.input("Persona key to delete: ").strip().lower()
                if key in BUILTIN_PERSONAS:
                    console.print("[yellow]Cannot delete built-in persona.[/yellow]")
                    continue
                deleted = remove_custom_persona(key)
                if deleted:
                    console.print(f"[green]Deleted custom persona:[/green] {key}")
                else:
                    console.print("[yellow]Persona not found.[/yellow]")
                continue
            console.print("[yellow]Unknown action. Use list, add, edit, delete, or back.[/yellow]")

    def choose_manual_agents() -> list[str] | None:
        active = get_active_personas()
        keys = list(active.keys())
        if len(keys) < 2:
            console.print("[bold red]Need at least two personas to run a debate.[/bold red]")
            return None
        list_personas()
        first = console.input("Manual agent 1 key: ").strip()
        second = console.input("Manual agent 2 key: ").strip()
        if first not in active or second not in active or first == second:
            console.print("[bold red]Invalid manual selection. Please choose two distinct valid keys.[/bold red]")
            return None
        return [first, second]

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

        if user_input == "/help":
            print_help()
            continue

        if user_input == "/personas":
            manage_personas()
            refresh_personas()
            continue

        if user_input == "/sessions":
            chat_history, selection_mode, current_session_name = manage_sessions()
            continue

        if user_input == "/mode":
            mode = console.input("Choose mode (auto/manual): ").strip().lower()
            if mode in {"auto", "manual"}:
                selection_mode = mode
                console.print(f"[green]Selection mode set to:[/green] {selection_mode}")
            else:
                console.print("[yellow]Invalid mode. Use auto or manual.[/yellow]")
            continue

        try:
            selected_agents = choose_manual_agents() if selection_mode == "manual" else None
            if selection_mode == "manual" and not selected_agents:
                continue
            chat_history = run_debate(
                user_input,
                chat_history,
                selection_mode=selection_mode,
                selected_agents=selected_agents,
            )
            if current_session_name:
                try:
                    session_store.save_session(current_session_name, chat_history, selection_mode)
                except Exception:
                    pass
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
