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

## Feature 2: Tool-Using Personas (Wikipedia + Calculator)

### What I Built

Gave debate personas access to **Wikipedia search** and a **calculator** tool so they can research real facts and compute statistics during openings and rebuttals. Added a UI toggle to enable/disable tools, and collapsible tool badges in the transcript showing what each persona researched.

### LangGraph / LangChain Concepts Learned

#### 1. `@tool` Decorator — Defining Tools
- `from langchain_core.tools import tool`
- Decorate a plain Python function with `@tool` to make it callable by an LLM
- The function's **docstring** is critical — it's what the LLM reads to decide when to use the tool
- The function signature (param names + types) becomes the tool's input schema automatically
- Tools return strings — the LLM consumes the result as text context

#### 2. `.bind_tools()` — Making an LLM Tool-Aware
- `ChatOpenAI(model=...).bind_tools([tool1, tool2])` creates a new LLM instance that knows about the tools
- The bound LLM can choose to call tools in its response via `response.tool_calls`
- If the LLM doesn't want to use tools, `tool_calls` is empty and `response.content` has normal text
- You need a **separate** LLM instance for tool-bound calls vs plain calls — can't toggle tools on a single instance

#### 3. ReAct Pattern — Agent Loop Inside a Node
- The ReAct (Reason + Act) loop is the core pattern for tool-using agents:
  1. Call LLM with tools bound → get response
  2. If response has `tool_calls` → execute tools → append results → call LLM again
  3. Repeat until LLM returns text (no tool calls)
  4. Return final text
- I implemented this as an **inner loop within each node** rather than as separate graph nodes — keeps the debate graph structure clean
- Key insight: tool usage is an **implementation detail** of how a persona builds its argument, not a separate debate stage

#### 4. Tool Call Message Protocol
- When the LLM requests a tool call, you must:
  1. Append the LLM's response (containing tool_calls) to the message list
  2. Execute the tool and append a message with `role: "tool"`, `content: <result>`, `tool_call_id: <id>`
  3. The `tool_call_id` links the result back to the specific tool call — required by the API
- This follows the OpenAI function-calling message format that LangChain wraps

#### 5. `Annotated` Reducers — Handling Parallel State Writes
- When two nodes run in parallel (e.g., agent_1_opening + agent_2_opening) and both write to the same state key, LangGraph throws: *"Can receive only one value per step"*
- Fix: Use `Annotated[list[dict], operator.add]` as the type annotation — this tells LangGraph to **merge** lists from parallel nodes instead of replacing
- Same pattern as `chat_history: Annotated[list, add_messages]` — reducers define how concurrent writes merge
- Without a reducer, each key can only be written by one node per step

#### 6. Tool Safety — No `eval()`
- For the calculator, used `numexpr.evaluate()` instead of Python's `eval()` — `numexpr` only handles math expressions and cannot execute arbitrary code
- This is an OWASP best practice — never let user-influenced strings reach `eval()`

### Architecture Decisions

| Decision | Why |
|---|---|
| ReAct loop inside nodes (not new graph nodes) | Keeps the main debate graph unchanged — tool calls are an implementation detail |
| Max 3 tool calls per node | Prevents infinite loops if the LLM keeps wanting to research |
| Wikipedia + Calculator only | Free, no extra API keys, sufficient for learning tool-calling patterns |
| Openings + rebuttals use tools, closings + synthesis don't | Closings summarize existing arguments (no new research), synthesis is a neutral moderator |
| `use_tools` toggle with default `True` | Backward compatible — tools on by default, can be disabled |
| `tools_used` with `operator.add` reducer | Parallel opening nodes both write tool records — reducer merges them |
| Tool records tagged with `node` field | UI can display tool badges per round (opening vs rebuttal) |

### Files Changed

| File | What Changed |
|---|---|
| `tools.py` (new) | `@tool` definitions for `wikipedia_search` and `calculator`, `DEBATE_TOOLS` list |
| `state.py` | Added `tools_used: Annotated[list[dict], operator.add]` and `use_tools: NotRequired[bool]` |
| `graph.py` | Added `_tool_llm` with `.bind_tools()`, `_agent_invoke_with_tools()` ReAct loop, updated opening/rebuttal nodes |
| `core/orchestration.py` | Added `use_tools` param, initialized `tools_used: []`, fixed `tools_used` merge logic in SSE streaming |
| `backend/schemas.py` | Added `use_tools: bool = True` to `DebateRequest` |
| `backend/routes/debates.py` | Threaded `use_tools` through `/stream` and `/run` endpoints |
| `frontend/src/App.jsx` | `ToolBadges` component, `useTools` state + checkbox toggle, badges in transcript + review panel |
| `frontend/src/styles.css` | `.tool-usage`, `.tool-badge`, `.tool-result`, `.tools-toggle` styles |
| `requirements.txt` | Added `wikipedia`, `numexpr` |

### Issues Faced & Resolutions

#### Issue 1: "Can receive only one value per step" — Parallel State Write Conflict
**Error**: `At key 'tools_used': Can receive only one value per step. Use an Annotated key to handle multiple values.`

**Root Cause**: `agent_1_opening` and `agent_2_opening` nodes run **in parallel** (both fan out from `route`). Both return `{"tools_used": [...]}`. LangGraph's default behavior is to assign the value, but with two concurrent writes to the same key it can't pick one.

**Fix**: Changed `tools_used` from `NotRequired[list[dict]]` to `Annotated[list[dict], operator.add]` — the `operator.add` reducer tells LangGraph to concatenate the lists from parallel nodes.

**Lesson**: Any state key written by parallel nodes **must** have a reducer. Use `operator.add` for lists, `add_messages` for message lists.

#### Issue 2: Tool Badges Not Showing in Frontend — SSE `result.update()` Overwrites
**Symptom**: Backend logs showed tool calls happening (🔧 lines), SSE events carried `tools_used`, but the final `DebateTranscript` rendered with no badges.

**Root Cause**: Two layers of the problem:
1. The orchestration layer's `result` dict used `result.update(node_output)` — when parallel opening nodes both emit `tools_used`, the second one's `update()` **replaces** the first's list instead of merging
2. The `DebateTranscript` component only renders after `result.synthesis` exists (full debate complete), but during the human-review pause, the review panel was showing openings **without** `ToolBadges`

**Fix**:
1. Added merge logic in `stream_debate_updates()` and `resume_debate_updates()`: if `tools_used` already exists in `result`, concatenate instead of replace
2. Seeded `tools_used` from the checkpoint state in `resume_debate_updates()` so rebuttal tool records get appended to opening tool records
3. Added `<ToolBadges>` to the review panel's opening cards — so users see tool badges at the human-review pause too

**Lesson**: LangGraph's state reducer (`operator.add`) only applies inside the graph. Your own result-accumulation dict outside the graph must implement the same merge logic manually.

#### Issue 3: Wikipedia Disambiguation Errors
**Symptom**: `wikipedia_search("Mars planet")` returned "No Wikipedia page found" or crashed on `DisambiguationError`.

**Root Cause**: The `wikipedia` Python library's `wikipedia.summary()` with `auto_suggest=True` sometimes resolves to the wrong disambiguation page. "Mars" resolves to "Mar" (an Aramaic word) which then hits a `DisambiguationError`.

**Fix**: Changed to a two-step approach: `wikipedia.search(query, results=5)` first, then iterate through results trying `wikipedia.summary(title, auto_suggest=False)` on each until one succeeds without errors.

**Lesson**: Always use `wikipedia.search()` first to get valid page titles, then `summary()` with `auto_suggest=False` on the result.

---

## Feature 3: Reflection Loop

*Coming next...*

*Coming next...*
