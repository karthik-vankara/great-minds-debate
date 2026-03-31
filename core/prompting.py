from typing import Any


def _trim_content(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def build_recent_chat_context(
    chat_history: list[dict[str, Any]] | None,
    max_messages: int = 6,
    max_chars_per_message: int = 400,
) -> str:
    if not chat_history:
        return ""

    recent = chat_history[-max_messages:]
    lines: list[str] = []

    for item in recent:
        role = str(item.get("role", "unknown")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role == "assistant":
            speaker = "Assistant"
        elif role == "user":
            speaker = "User"
        else:
            speaker = "Context"

        lines.append(f"{speaker}: {_trim_content(content, max_chars_per_message)}")

    if not lines:
        return ""

    return "Recent conversation context (oldest to newest):\n" + "\n".join(lines)
