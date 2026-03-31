"""Smoke test — verifies all project modules import cleanly and OPENAI_API_KEY is set."""
import os
from dotenv import load_dotenv

load_dotenv()


def test_imports():
    from state import DebateState
    from personas import PERSONAS, AGENT_KEYS
    from router import route_node
    from graph import app
    from core.prompting import build_recent_chat_context
    from core.orchestration import run_debate_orchestration
    print("[OK] All modules imported successfully.")
    print(f"[OK] Agents available: {', '.join(AGENT_KEYS)}")


def test_env():
    key = os.environ.get("OPENAI_API_KEY", "")
    assert key, "OPENAI_API_KEY is not set — add it to your .env file"
    print(f"[OK] OPENAI_API_KEY is set ({key[:8]}...)")


if __name__ == "__main__":
    test_env()
    test_imports()
    print("\nAll checks passed. Run `python main.py` to start the debate arena.")
