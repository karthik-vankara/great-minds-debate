from datetime import datetime

from rich.panel import Panel

from app_state import AppState
from personas import (
    BUILTIN_PERSONAS,
    refresh_personas,
    remove_custom_persona,
    save_custom_persona,
)
from session_store import SessionStore


def print_help(console) -> None:
    console.print(Panel(
        "[bold]/personas[/bold] Manage personas (list/add/edit/delete)\n"
        "[bold]/sessions[/bold] Manage chat sessions (list/save/load/delete)\n"
        "[bold]/mode[/bold] Switch between auto and manual selection\n"
        "[bold]/help[/bold] Show this help",
        title="[bold white]Commands[/bold white]",
        border_style="white",
    ))


def list_personas(console, state: AppState) -> None:
    lines = []
    for key, data in state.active_personas().items():
        origin = "built-in" if key in BUILTIN_PERSONAS else "custom"
        lines.append(f"[bold]{key}[/bold] ({origin}) - {data['display_name']}")
    console.print(Panel("\n".join(lines), title="[bold white]Personas[/bold white]", border_style="white"))


def prompt_persona_payload(console, existing: dict | None = None) -> dict:
    existing = existing or {}
    display_name = console.input(f"Display name [{existing.get('display_name', '')}]: ").strip() or existing.get("display_name", "")
    color = console.input(f"Color [{existing.get('color', 'bold white')}]: ").strip() or existing.get("color", "bold white")
    tags_input = console.input(f"Tags comma-separated [{', '.join(existing.get('tags', []))}]: ").strip()
    system_prompt = console.input("System prompt: ").strip() or existing.get("system_prompt", "")
    tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()] if tags_input else existing.get("tags", [])
    return {
        "display_name": display_name,
        "color": color,
        "tags": tags,
        "system_prompt": system_prompt,
    }


def manage_personas(console, state: AppState) -> None:
    while True:
        console.print("\n[bold]Persona Manager[/bold] - choose: list, add, edit, delete, back")
        action = console.input("persona> ").strip().lower()
        if action == "back":
            return
        if action == "list":
            list_personas(console, state)
            continue
        if action == "add":
            key = console.input("New persona key (snake_case): ").strip().lower()
            if not key:
                console.print("[yellow]Persona key is required.[/yellow]")
                continue
            payload = prompt_persona_payload(console)
            try:
                save_custom_persona(key, payload)
                refresh_personas()
                console.print(f"[green]Saved custom persona:[/green] {key}")
            except Exception as exc:
                console.print(f"[bold red]Failed to save persona:[/bold red] {exc}")
            continue
        if action == "edit":
            key = console.input("Persona key to edit: ").strip().lower()
            active = state.active_personas()
            if key in BUILTIN_PERSONAS:
                console.print("[yellow]Built-in personas are immutable. Create a new custom key instead.[/yellow]")
                continue
            if key not in active:
                console.print("[yellow]Persona not found.[/yellow]")
                continue
            payload = prompt_persona_payload(console, active[key])
            try:
                save_custom_persona(key, payload)
                refresh_personas()
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
            refresh_personas()
            if deleted:
                console.print(f"[green]Deleted custom persona:[/green] {key}")
            else:
                console.print("[yellow]Persona not found.[/yellow]")
            continue
        console.print("[yellow]Unknown action. Use list, add, edit, delete, or back.[/yellow]")


def choose_manual_agents(console, state: AppState) -> list[str] | None:
    active = state.active_personas()
    if len(active) < 2:
        console.print("[bold red]Need at least two personas to run a debate.[/bold red]")
        return None
    list_personas(console, state)
    first = console.input("Manual agent 1 key: ").strip()
    second = console.input("Manual agent 2 key: ").strip()
    if first not in active or second not in active or first == second:
        console.print("[bold red]Invalid manual selection. Please choose two distinct valid keys.[/bold red]")
        return None
    return [first, second]


def manage_sessions(console, state: AppState, session_store: SessionStore) -> None:
    while True:
        console.print("\n[bold]Session Manager[/bold] - choose: list, save, load, delete, back")
        action = console.input("session> ").strip().lower()
        if action == "back":
            return

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
            default_name = state.current_session_name or datetime.now().strftime("session_%Y%m%d_%H%M%S")
            name = console.input(f"Session name [{default_name}]: ").strip() or default_name
            try:
                saved_name = session_store.save_session(name, state.chat_history, state.selection_mode)
                state.current_session_name = saved_name
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
                state.restore_session(loaded)
                console.print(
                    f"[green]Loaded session:[/green] {state.current_session_name} "
                    f"(messages={len(state.chat_history)}, mode={state.selection_mode})"
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
                    if state.current_session_name == name:
                        state.current_session_name = None
                    console.print(f"[green]Deleted session:[/green] {name}")
                else:
                    console.print("[yellow]Session not found.[/yellow]")
            except Exception as exc:
                console.print(f"[bold red]Failed to delete session:[/bold red] {exc}")
            continue

        console.print("[yellow]Unknown action. Use list, save, load, delete, or back.[/yellow]")


def show_welcome(console) -> None:
    console.print(Panel(
        "[bold]Welcome to the AI Persona Debate Arena![/bold]\n\n"
        "Ask any idea or question and watch [cyan]Steve Jobs[/cyan], [yellow]Elon Musk[/yellow], "
        "[green]Einstein[/green], and [blue]Zuckerberg[/blue] debate it.\n\n"
        "Commands: [bold]/personas[/bold], [bold]/sessions[/bold], [bold]/mode[/bold], [bold]/help[/bold].\n"
        "Type [bold red]quit[/bold red] or [bold red]exit[/bold red] to stop.",
        title="[bold magenta]🎤 DEBATE ARENA[/bold magenta]",
        border_style="magenta",
    ))


def print_runtime_status(console, state: AppState) -> None:
    session_name = state.current_session_name or "none"
    console.print(
        f"[dim]mode={state.selection_mode} | session={session_name} | personas={len(state.active_personas())}[/dim]"
    )