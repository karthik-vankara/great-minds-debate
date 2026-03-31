from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_session_store
from backend.schemas import SessionLoadResponse, SessionSaveRequest, SessionSummary
from session_store import SessionStore


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(session_store: SessionStore = Depends(get_session_store)) -> list[SessionSummary]:
    return [SessionSummary(**item) for item in session_store.list_sessions()]


@router.post("/save")
def save_session(payload: SessionSaveRequest, session_store: SessionStore = Depends(get_session_store)) -> dict[str, str]:
    try:
        name = session_store.save_session(payload.name, payload.chat_history, payload.selection_mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": name}


@router.get("/{name}", response_model=SessionLoadResponse)
def load_session(name: str, session_store: SessionStore = Depends(get_session_store)) -> SessionLoadResponse:
    try:
        loaded = session_store.load_session(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SessionLoadResponse(**loaded)


@router.delete("/{name}")
def delete_session(name: str, session_store: SessionStore = Depends(get_session_store)) -> dict[str, bool]:
    try:
        deleted = session_store.delete_session(name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {"deleted": True}
