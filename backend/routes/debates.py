import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.dependencies import get_session_store
from backend.schemas import DebateRequest, DebateResumeRequest, DebateResponse
from core.orchestration import stream_debate_updates, resume_debate_updates, run_debate_orchestration, finalize_chat_history
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


@router.post("/stream")
def stream_debate_endpoint(payload: DebateRequest, session_store: SessionStore = Depends(get_session_store)):
    """Stream debate updates via Server-Sent Events (SSE)."""
    if payload.selection_mode == "manual" and len(payload.selected_agents) != 2:
        raise HTTPException(status_code=400, detail="Manual mode requires exactly two selected agent keys.")

    persona_pool = get_active_personas()
    
    def event_generator():
        try:
            last_result = {}
            for node_name, node_output, result in stream_debate_updates(
                payload.user_input,
                payload.chat_history,
                persona_pool,
                selection_mode=payload.selection_mode,
                selected_agents=payload.selected_agents,
            ):
                if node_name == "__interrupt__":
                    # Graph paused at human_review — send waiting event
                    waiting_event = {
                        "node": "waiting_for_input",
                        "debate_id": node_output["debate_id"],
                        "result": result,
                    }
                    yield f"data: {json.dumps(waiting_event)}\n\n"
                    return  # End SSE stream — client must call /resume

                last_result = result
                event_data = {
                    "node": node_name,
                    "output": node_output,
                    "result": result,
                }
                yield f"data: {json.dumps(event_data)}\n\n"
            
            # If we get here, no interrupt occurred (shouldn't happen with current graph)
            # but handle gracefully for backward compat
            saved_session_name = _save_session_if_needed(
                session_store, payload.session_name, payload.chat_history,
                payload.user_input, last_result, payload.selection_mode,
            )
            if saved_session_name == "__error__":
                return

            synthesis = last_result.get("synthesis", "")
            final_chat_history = finalize_chat_history(
                payload.chat_history, payload.user_input, synthesis,
            )
            completion_event = {
                "node": "completion",
                "saved_session_name": saved_session_name,
                "chat_history": final_chat_history,
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as exc:
            error_event = {"node": "error", "error": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/resume")
def resume_debate_endpoint(payload: DebateResumeRequest, session_store: SessionStore = Depends(get_session_store)):
    """Resume a paused debate after human review via SSE."""

    def event_generator():
        try:
            last_result = {}
            for node_name, node_output, result in resume_debate_updates(
                payload.debate_id,
                human_feedback=payload.human_feedback,
                skip_to_synthesis=payload.skip_to_synthesis,
            ):
                last_result = result
                event_data = {
                    "node": node_name,
                    "output": node_output,
                    "result": result,
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            saved_session_name = _save_session_if_needed(
                session_store, payload.session_name, payload.chat_history,
                payload.user_input, last_result, "auto",
            )

            synthesis = last_result.get("synthesis", "")
            final_chat_history = finalize_chat_history(
                payload.chat_history, payload.user_input, synthesis,
            )
            completion_event = {
                "node": "completion",
                "saved_session_name": saved_session_name,
                "chat_history": final_chat_history,
            }
            yield f"data: {json.dumps(completion_event)}\n\n"

        except Exception as exc:
            error_event = {"node": "error", "error": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _save_session_if_needed(
    session_store: SessionStore,
    session_name: str | None,
    chat_history: list,
    user_input: str,
    last_result: dict,
    selection_mode: str,
) -> str | None:
    if not session_name:
        return None
    try:
        synthesis = last_result.get("synthesis", "")
        final_chat_history = finalize_chat_history(chat_history, user_input, synthesis)
        return session_store.save_session(session_name, final_chat_history, selection_mode)
    except Exception:
        return None
