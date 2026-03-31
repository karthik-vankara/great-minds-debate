import json
from copy import deepcopy
from pathlib import Path


BUILTIN_PERSONAS: dict[str, dict] = {
    "steve_jobs": {
        "display_name": "Steve Jobs",
        "color": "bold cyan",
        "tags": [
            "product design", "UX", "simplicity", "consumer tech",
            "storytelling", "Apple", "iPhone", "design thinking",
            "branding", "user experience", "hardware", "software integration",
        ],
        "system_prompt": (
            "You are Steve Jobs — visionary co-founder of Apple, master of product design "
            "and simplicity. You believe technology should be invisible and beautiful. "
            "You are blunt, perfectionist, and deeply passionate about the intersection "
            "of technology and the liberal arts. You never accept mediocrity. "
            "You speak with conviction, use vivid analogies, and always bring the "
            "argument back to the end-user experience. Keep responses focused and punchy — "
            "no fluff, no jargon for jargon's sake."
        ),
    },
    "elon_musk": {
        "display_name": "Elon Musk",
        "color": "bold yellow",
        "tags": [
            "space", "electric vehicles", "AI", "first-principles thinking",
            "Tesla", "SpaceX", "X", "Neuralink", "disruption", "energy",
            "autonomous vehicles", "physics-based reasoning", "big bets",
            "multi-planetary", "engineering", "rockets",
        ],
        "system_prompt": (
            "You are Elon Musk — entrepreneur, engineer, and founder of Tesla, SpaceX, "
            "and Neuralink. You reason from first principles, challenge assumptions, "
            "and think in orders of magnitude. You are bold, sometimes contrarian, "
            "and willing to make enormous bets on the future of humanity. "
            "You love physics-based analogies and often call out conventional thinking "
            "as 'reasoning by analogy' rather than reasoning from first principles. "
            "Be direct, energetic, and back your arguments with technical or scientific logic."
        ),
    },
    "einstein": {
        "display_name": "Albert Einstein",
        "color": "bold green",
        "tags": [
            "physics", "relativity", "quantum mechanics", "mathematics",
            "thought experiments", "philosophy of science", "curiosity",
            "space-time", "energy", "theoretical physics", "Nobel Prize",
            "pacifism", "education", "imagination", "scientific method",
        ],
        "system_prompt": (
            "You are Albert Einstein — theoretical physicist, author of the theory of "
            "relativity, and one of the greatest scientific minds in history. "
            "You approach every problem through thought experiments and first-principles "
            "curiosity. You are philosophical, humble yet confident in your reasoning, "
            "and deeply believe that imagination is more important than knowledge. "
            "You often use elegant analogies from nature and physics. "
            "Challenge assumptions gently, and always seek the deeper truth behind a question."
        ),
    },
    "zuckerberg": {
        "display_name": "Mark Zuckerberg",
        "color": "bold blue",
        "tags": [
            "social media", "metaverse", "AR", "VR", "connectivity",
            "Facebook", "Meta", "Instagram", "WhatsApp", "data",
            "network effects", "scale", "community", "builder mentality",
            "software", "product growth", "social graphs", "open source",
        ],
        "system_prompt": (
            "You are Mark Zuckerberg — founder and CEO of Meta, builder of the world's "
            "largest social network. You think analytically and at massive scale. "
            "You are obsessed with connectivity, community, and the long-term future "
            "of the open metaverse and mixed reality. You are a builder at heart — "
            "you believe in moving fast, shipping, and iterating. "
            "Data drives your decisions. You are measured, sometimes robotic in delivery, "
            "but deeply strategic. Focus on network effects, scale, and how technology "
            "connects people."
        ),
    },
}


class PersonaRepository:
    """Persona storage abstraction with JSON backend for custom personas."""

    def __init__(self, storage_path: str | Path = ".debate_arena/personas/custom_personas.json") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_payload(self) -> dict:
        if not self.storage_path.exists():
            return {"schema_version": 1, "personas": {}}

        try:
            with self.storage_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {"schema_version": 1, "personas": {}}

        if not isinstance(payload, dict):
            return {"schema_version": 1, "personas": {}}

        if "personas" not in payload or not isinstance(payload["personas"], dict):
            payload["personas"] = {}
        if "schema_version" not in payload:
            payload["schema_version"] = 1

        return payload

    def _write_payload(self, payload: dict) -> None:
        with self.storage_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=True)

    def list_custom_personas(self) -> dict[str, dict]:
        payload = self._read_payload()
        personas = payload.get("personas", {})
        cleaned: dict[str, dict] = {}
        for key, data in personas.items():
            if _is_valid_persona(key, data):
                cleaned[key] = _normalize_persona(data)
        return cleaned

    def upsert_custom_persona(self, key: str, data: dict) -> None:
        if key in BUILTIN_PERSONAS:
            raise ValueError(f"Cannot overwrite built-in persona: {key}")
        if not _is_valid_persona(key, data):
            raise ValueError("Invalid persona payload.")

        payload = self._read_payload()
        payload["personas"][key] = _normalize_persona(data)
        self._write_payload(payload)

    def delete_custom_persona(self, key: str) -> bool:
        payload = self._read_payload()
        personas = payload.get("personas", {})
        if key not in personas:
            return False
        del personas[key]
        payload["personas"] = personas
        self._write_payload(payload)
        return True

    def merged_personas(self) -> dict[str, dict]:
        merged = deepcopy(BUILTIN_PERSONAS)
        merged.update(self.list_custom_personas())
        return merged


def _is_valid_persona(key: str, data: dict) -> bool:
    if not isinstance(key, str) or not key or " " in key:
        return False
    if not isinstance(data, dict):
        return False
    required_fields = ("display_name", "color", "tags", "system_prompt")
    for field in required_fields:
        if field not in data:
            return False
    if not isinstance(data["display_name"], str) or not data["display_name"].strip():
        return False
    if not isinstance(data["color"], str) or not data["color"].strip():
        return False
    if not isinstance(data["system_prompt"], str) or not data["system_prompt"].strip():
        return False
    if not isinstance(data["tags"], list) or not data["tags"]:
        return False
    if any(not isinstance(tag, str) or not tag.strip() for tag in data["tags"]):
        return False
    return True


def _normalize_persona(data: dict) -> dict:
    unique_tags = []
    seen_tags = set()
    for raw_tag in data.get("tags", []):
        normalized = raw_tag.strip().lower()
        if normalized and normalized not in seen_tags:
            unique_tags.append(normalized)
            seen_tags.add(normalized)

    return {
        "display_name": data["display_name"].strip(),
        "color": data["color"].strip(),
        "tags": unique_tags,
        "system_prompt": data["system_prompt"].strip(),
    }


_REPOSITORY = PersonaRepository()


def get_active_personas() -> dict[str, dict]:
    return _REPOSITORY.merged_personas()


def refresh_personas() -> tuple[dict[str, dict], list[str]]:
    global PERSONAS, AGENT_KEYS
    PERSONAS = get_active_personas()
    AGENT_KEYS = list(PERSONAS.keys())
    return PERSONAS, AGENT_KEYS


def save_custom_persona(key: str, data: dict) -> None:
    _REPOSITORY.upsert_custom_persona(key, data)
    refresh_personas()


def remove_custom_persona(key: str) -> bool:
    deleted = _REPOSITORY.delete_custom_persona(key)
    refresh_personas()
    return deleted


PERSONAS, AGENT_KEYS = refresh_personas()
