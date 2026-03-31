from dataclasses import dataclass, field

from personas import get_active_personas


@dataclass
class AppState:
    chat_history: list = field(default_factory=list)
    selection_mode: str = "auto"
    current_session_name: str | None = None

    def active_personas(self) -> dict[str, dict]:
        return get_active_personas()

    def restore_session(self, loaded_session: dict) -> None:
        self.chat_history = loaded_session["chat_history"]
        self.selection_mode = loaded_session["selection_mode"]
        self.current_session_name = loaded_session["name"]
