from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_session_store
from backend.schemas import DebateRequest, DebateResponse
from core.orchestration import run_debate_orchestration
from personas import get_active_personas
from session_store import SessionStore


router = APIRouter(prefix="/debates", tags=["debates"])


@router.post("/run", response_model=DebateResponse)
def run_debate_endpoint(payload: DebateRequest, session_store: SessionStore = Depends(get_session_store)) -> DebateResponse:
    if payload.selection_mode == "manual" and len(payload.selected_agents) != 2:
        raise HTTPException(status_code=400, detail="Manual mode requires exactly two selected agent keys.")

    persona_pool = get_active_personas()

    try:
        outcome = run_debate_orchestration(
            payload.user_input,
            payload.chat_history,
            persona_pool,
            selection_mode=payload.selection_mode,
            selected_agents=payload.selected_agents,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Debate execution failed: {exc}") from exc

    saved_session_name: str | None = None
    if payload.session_name:
        try:
            saved_session_name = session_store.save_session(
                payload.session_name,
                outcome["chat_history"],
                payload.selection_mode,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Session save failed: {exc}") from exc

    return DebateResponse(
        events=outcome["events"],
        result=outcome["result"],
        chat_history=outcome["chat_history"],
        saved_session_name=saved_session_name,
    )
