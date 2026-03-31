import json
from datetime import datetime, timezone
from pathlib import Path


class SessionStore:
    """Persist debate sessions to JSON files."""

    def __init__(self, root_dir: str | Path = ".debate_arena/sessions") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, name: str) -> Path:
        safe_name = "".join(ch for ch in name.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        if not safe_name:
            raise ValueError("Session name must include letters, numbers, '_' or '-'.")
        return self.root_dir / f"{safe_name}.json"

    def list_sessions(self) -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.root_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items.append(
                    {
                        "name": path.stem,
                        "updated_at": payload.get("updated_at", "unknown"),
                        "messages": len(payload.get("chat_history", [])),
                        "selection_mode": payload.get("selection_mode", "auto"),
                    }
                )
            except (OSError, json.JSONDecodeError):
                items.append(
                    {
                        "name": path.stem,
                        "updated_at": "corrupt",
                        "messages": 0,
                        "selection_mode": "unknown",
                    }
                )
        return items

    def save_session(self, name: str, chat_history: list, selection_mode: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        path = self._session_path(name)
        payload = {
            "schema_version": 1,
            "name": path.stem,
            "updated_at": now,
            "selection_mode": selection_mode,
            "chat_history": chat_history,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return path.stem

    def load_session(self, name: str) -> dict:
        path = self._session_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Session '{name}' not found.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid session payload.")

        chat_history = payload.get("chat_history", [])
        if not isinstance(chat_history, list):
            chat_history = []

        selection_mode = payload.get("selection_mode", "auto")
        if selection_mode not in {"auto", "manual"}:
            selection_mode = "auto"

        return {
            "name": payload.get("name", path.stem),
            "chat_history": chat_history,
            "selection_mode": selection_mode,
            "updated_at": payload.get("updated_at", "unknown"),
        }

    def delete_session(self, name: str) -> bool:
        path = self._session_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True
