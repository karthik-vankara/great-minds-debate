# Learning Notes — AI Persona Debate Arena

Feature-wise notes on what I learned, issues I faced, and how I resolved them.

---

## Feature 1: Human-in-the-Loop (Checkpointing + Interrupts)

### What I Built

Added the ability for the debate to **pause after opening statements** so the user can review both agents' openings and decide how to proceed:
- **Continue** — rebuttals proceed normally
- **Redirect** — provide feedback that agents incorporate into their rebuttals
- **Skip to Synthesis** — jump straight to the final summary, skipping rebuttals and closings

### LangGraph Concepts Learned

#### 1. Checkpointing (`MemorySaver`)
- LangGraph graphs are stateless by default — each `.stream()` call is a one-shot run
- Adding a **checkpointer** to `builder.compile(checkpointer=MemorySaver())` makes the graph stateful — it persists the full state after each node execution
- `MemorySaver` stores state in-memory (good for dev, lost on server restart). Production would use `SqliteSaver` or `PostgresSaver`
- Each execution needs a unique `thread_id` in `config={"configurable": {"thread_id": "..."}}` so the checkpointer can track it

#### 2. `interrupt()` — Pausing Graph Execution
- `from langgraph.types import interrupt`
- Calling `interrupt(value)` inside a node **halts the graph** and returns control to the caller
- The `value` passed to `interrupt()` is metadata sent back (I used it to send opening statements + agent info)
- After `interrupt()`, the graph's `stream()` loop ends — the caller must detect this and resume later
- Detection: call `app.get_state(config)` after streaming ends and check `state_snapshot.next` — if non-empty, the graph is paused

#### 3. `Command(resume=True)` — Resuming Execution
- `from langgraph.types import Command`
- To resume a paused graph: `app.stream(Command(resume=True), config=config)`
- This continues execution from exactly where it paused (after the `interrupt()` call)
- The resumed graph picks up all state accumulated before the interrupt

#### 4. `app.update_state()` — Injecting Human Input
- Before resuming, inject human decisions into the graph state: `app.update_state(config, {"human_feedback": "...", "skip_to_synthesis": True}, as_node="human_review")`
- `as_node` tells LangGraph which node "wrote" this state update — important for the graph to know where to resume from
- Downstream nodes (rebuttals) can then read `state.get("human_feedback")` and act on it

#### 5. Conditional Edges — Dynamic Graph Routing
- `builder.add_conditional_edges("human_review", router_function)` lets the graph take different paths based on state
- My router returns `["synthesis"]` if `skip_to_synthesis` is True, or `["agent_1_rebuttal", "agent_2_rebuttal"]` otherwise
- This is how I implemented the "skip to synthesis" shortcut — the graph literally takes a different path

#### 6. Thread IDs — Multi-Session Support
- Each debate gets a unique `thread_id` (UUID4), allowing multiple debates to be paused simultaneously
- The frontend stores the `debate_id` returned in the `waiting_for_input` SSE event and sends it back when resuming
- The checkpointer uses thread_id as the lookup key

### Architecture Decisions

| Decision | Why |
|---|---|
| `human_review_node` is a real graph node (not just an edge interrupt) | Appears in SSE events and graph visualization, cleaner separation |
| Interrupt after BOTH openings (not after each) | One review step is simpler UX than two |
| State update via `update_state()` + resume via `Command(resume=True)` separately | Cleaner than trying to combine both in one `Command()` call |
| `/debates/stream` ends on interrupt, `/debates/resume` is a separate endpoint | Clean HTTP semantics — each SSE stream has a single lifecycle |
| `run_debate_orchestration()` auto-resumes internally | Backward compatible — sync endpoint still works as a single call |

### Files Changed

| File | What Changed |
|---|---|
| `state.py` | Added `human_feedback`, `skip_to_synthesis`, `debate_id` fields to `DebateState` |
| `graph.py` | Added `MemorySaver`, `interrupt`, `human_review_node`, `_human_review_router`, `_feedback_block`, compile with checkpointer |
| `core/orchestration.py` | Added `thread_id` generation, interrupt detection, `resume_debate_updates()`, auto-resume in sync endpoint |
| `backend/schemas.py` | Added `DebateResumeRequest` model |
| `backend/routes/debates.py` | Modified `/stream` for `waiting_for_input` event, added `POST /resume` endpoint |
| `frontend/src/api/client.js` | Refactored SSE into shared `_streamSSE()`, added `resumeDebate()` |
| `frontend/src/App.jsx` | Added `reviewMode` state, review panel UI, Continue/Redirect/Skip handlers |
| `frontend/src/styles.css` | Added `.review-panel`, `.review-openings`, `.review-actions` styles |

### Issues Faced & Resolutions

#### Issue 1: Blank screen — `streamProgress.allNodes.length` crash
**Error**: `TypeError: undefined is not an object (evaluating 'streamProgress.allNodes.length')`

**Root Cause**: Race condition in React. When `waiting_for_input` arrives, the handler sets `streamProgress` to `null`. But the SSE reader then hits `done: true` and fires the `stream_complete` handler, which does `setStreamProgress(prev => ({ ...prev, currentNode: "Finalizing..." }))`. Spreading `null` creates `{ currentNode: "Finalizing..." }` — missing `allNodes`. React re-renders and crashes on `streamProgress.allNodes.length`.

**Fix**: 
1. Used optional chaining in JSX: `streamProgress.allNodes?.length > 0`
2. Guarded all `setStreamProgress` updater functions: `prev => prev ? ({ ...prev, ... }) : null` — if prev is already null, stay null
3. Applied to both `stream_complete` and `completion` handlers in both `handleRunDebate` and `handleResumeDebate`

**Lesson**: When using React state updater functions with spread (`...prev`), always guard against `prev` being `null`.

#### Issue 2: "cannot convert dictionary update sequence element #0 to a sequence"
**Error**: `data: {"node": "error", "error": "cannot convert dictionary update sequence element #0 to a sequence"}`

**Root Cause**: LangGraph's `stream_mode="updates"` emits a special `__interrupt__` event when the graph hits an `interrupt()` call. The event looks like `{"__interrupt__": (<tuple of interrupt data>,)}` — the value is a **tuple**, not a dict. My streaming loop called `result.update(node_output)` on that tuple, and `dict.update()` can't handle a tuple, causing the crash.

**Fix**: Added a guard in both streaming loops:
```python
for node_name, node_output in event.items():
    if node_name == "__interrupt__":
        continue  # LangGraph internal interrupt marker — skip it
    result.update(node_output)
    yield node_name, node_output, dict(result)
```

**Lesson**: LangGraph's `stream_mode="updates"` doesn't only emit your node outputs — it also emits internal events like `__interrupt__`. Always filter these out before processing.

#### Issue 3: First attempt at `Command(resume=True, update={...})` with state update
**What I Tried**: Combining state injection and resume in one call:
```python
Command(resume=True, update={"human_feedback": feedback, "skip_to_synthesis": skip})
```

**What Happened**: Same "cannot convert dictionary update sequence" error. The `update` param on `Command` has specific semantics and didn't work as expected for injecting state before resume.

**Fix**: Separated into two steps:
```python
# Step 1: Inject human input into the paused state
app.update_state(config, {"human_feedback": ..., "skip_to_synthesis": ...}, as_node="human_review")

# Step 2: Resume execution
app.stream(Command(resume=True), config=config, stream_mode="updates")
```

**Lesson**: Use `app.update_state()` to modify paused graph state, then `Command(resume=True)` to resume. Keep them separate — they are two distinct operations.

---

## Feature 2: Tool-Using Personas

*Coming next...*

## Feature 3: Reflection Loop

*Coming next...*
