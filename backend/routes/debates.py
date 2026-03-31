import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.dependencies import get_session_store
from backend.schemas import DebateRequest, DebateResponse
from core.orchestration import stream_debate_updates, run_debate_orchestration
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
                last_result = result
                # Send SSE event with stream data
                event_data = {
                    "node": node_name,
                    "output": node_output,
                    "result": result,
                }
                yield f"data: {json.dumps(event_data)}\n\n"
            
            # Save session if requested (send as final event marker)
            saved_session_name = None
            if payload.session_name:
                try:
                    # Reconstruct final chat history
                    synthesis = last_result.get("synthesis", "")
                    final_chat_history = list(payload.chat_history) + [
                        {"role": "user", "content": payload.user_input},
                        {"role": "assistant", "content": synthesis},
                    ]
                    saved_session_name = session_store.save_session(
                        payload.session_name,
                        final_chat_history,
                        payload.selection_mode,
                    )
                except Exception as exc:
                    error_event = {
                        "node": "session_save_error",
                        "error": str(exc),
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    return
            
            # Build final chat history with the new turn
            synthesis = last_result.get("synthesis", "")
            final_chat_history = list(payload.chat_history) + [
                {"role": "user", "content": payload.user_input},
                {"role": "assistant", "content": synthesis},
            ]

            # Send completion marker with final chat history
            completion_event = {
                "node": "completion",
                "saved_session_name": saved_session_name,
                "chat_history": final_chat_history,
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as exc:
            error_event = {
                "node": "error",
                "error": str(exc),
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
