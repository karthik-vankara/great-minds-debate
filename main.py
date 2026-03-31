from dotenv import load_dotenv
from rich.console import Console

from app_state import AppState
from cli_handlers import (
    choose_manual_agents,
    manage_personas,
    manage_sessions,
    print_help,
    print_runtime_status,
    show_welcome,
)
from debate_runner import run_debate
from session_store import SessionStore

load_dotenv()

console = Console()
session_store = SessionStore()


def main():
    show_welcome(console)
    state = AppState()

    while True:
        console.print()
        print_runtime_status(console, state)
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
            print_help(console)
            continue

        if user_input == "/personas":
            manage_personas(console, state)
            continue

        if user_input == "/sessions":
            manage_sessions(console, state, session_store)
            continue

        if user_input == "/mode":
            mode = console.input("Choose mode (auto/manual): ").strip().lower()
            if mode in {"auto", "manual"}:
                state.selection_mode = mode
                console.print(f"[green]Selection mode set to:[/green] {state.selection_mode}")
            else:
                console.print("[yellow]Invalid mode. Use auto or manual.[/yellow]")
            continue

        try:
            selected_agents = choose_manual_agents(console, state) if state.selection_mode == "manual" else None
            if state.selection_mode == "manual" and not selected_agents:
                continue
            state.chat_history = run_debate(
                console,
                user_input,
                state.chat_history,
                state.active_personas(),
                selection_mode=state.selection_mode,
                selected_agents=selected_agents,
            )
            if state.current_session_name:
                try:
                    session_store.save_session(state.current_session_name, state.chat_history, state.selection_mode)
                except Exception:
                    pass
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
