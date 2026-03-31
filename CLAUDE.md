# CLAUDE.md - AI Persona Debate Arena

## Project Overview

**AI Persona Debate Arena** — a multi-interface platform where AI personas (e.g., Steve Jobs, Elon Musk, Einstein) debate user-submitted topics. Debates run through a LangGraph state machine with a router selecting personas, followed by opening statements, rebuttals, closing arguments, and a neutral synthesis.

Two interfaces exist: a CLI (terminal) and a Web UI (React/FastAPI), both sharing the same core orchestration layer.

## Tech Stack

- **Backend**: Python, FastAPI, LangGraph, LangChain OpenAI, Pydantic
- **Frontend**: React 18 + Vite (no UI framework/libraries, hand-written CSS)
- **Persistence**: JSON files under `.debate_arena/` (sessions + custom personas)
- **LLM config**: `DEBATE_MODEL` env var (default `gpt-4.1`), loaded via `python-dotenv` + LangChain

## Architecture

```
┌────────────┐     ┌──────────────────┐     ┌───────────────────────┐
│ React UI   │────▶│ FastAPI Backend   │────▶│ LangGraph Debate Graph │
│ (Vite)     │     │ /api/*            │     │ (graph.py)             │
└────────────┘     └──────────────────┘     └───────────────────────┘
                        │
                        ├── personas.py (PersonaRepository, BUILTIN_PERSONAS)
                        ├── session_store.py (SessionStore)
                        └── core/orchestration.py (shared debounce runner)
CLI (terminal) also calls core orchestration directly
```

### Key Files Map

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, CORS, routes registration |
| `backend/schemas.py` | Pydantic request/response models |
| `backend/routes/debates.py` | POST `/debates/run` (sync) + POST `/debates/stream` (SSE) |
| `backend/routes/personas.py` | CRUD for personas |
| `backend/routes/sessions.py` | CRUD for sessions |
| `backend/dependencies.py` | DI — singleton SessionStore |
| `core/orchestration.py` | `stream_debate_updates()` + `run_debate_orchestration()` — shared by API and CLI |
| `core/prompting.py` | `build_recent_chat_context()` — recent message trimming |
| `graph.py` | LangGraph `StateGraph` — debate nodes and edges |
| `state.py` | `DebateState` — TypedDict defining LangGraph state shape |
| `router.py` | `route_node` — persona router (auto/manual selection) |
| `personas.py` | `BUILTIN_PERSONAS` dict + `PersonaRepository` + upsert/delete helpers |
| `session_store.py` | `SessionStore` — JSON persistence for debate sessions |
| `frontend/src/App.jsx` | Single-page React UI |
| `frontend/src/api/client.js` | Fetch wrapper + SSE streaming consumer (`streamDebate()`) |
| `frontend/src/styles.css` | Hand-written CSS (Space Grotesk + IBM Plex Mono) |
| `docs/implementation-phases.md` | Phase-by-phase implementation history |

## Debate Graph Flow

The LangGraph in `graph.py` defines this sequence:

```
START → route → (agent_1_opening, agent_2_opening) [parallel]
       → agent_1_rebuttal → agent_1_closing → synthesis → END
       → agent_2_rebuttal → agent_2_closing → (joins synthesis)
```

**State shape** (`state.py`):
- `user_input` (str) — debate topic
- `chat_history` — annotated with `add_messages` reducer
- Router output: `agent_1`, `agent_2`, `agent_1_confidence`, `agent_2_confidence`, `routing_reason`
- Debate rounds: `*_opening`, `*_rebuttal`, `*_closing` for each agent
- `synthesis` — final neutral summary
- Optional: `available_personas`, `selection_mode`, `selected_agents`

## Environment Variables

Create `.env` from `.env.example`:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `DEBATE_MODEL` | No | `gpt-4.1` | Model used for debate responses and synthesis |
| `ROUTER_MODEL` | No | `gpt-4o-mini` | Model used for persona routing |

## Run Commands

**Backend (FastAPI):**
```
uvicorn backend.main:app --reload --port 8000
```

**Frontend (Vite):**
```
cd frontend && npm run dev
```
Serves at `http://127.0.0.1:5173`, proxies API to `http://127.0.0.1:8000/api`.

**CLI:**
```
python main.py
```

## Coding Conventions

- **Python**: Typed, Pydantic models for all API contracts. No external DB — JSON file storage via `SessionStore` and `PersonaRepository`.
- **Frontend**: Single `App.jsx` for all UI logic. No component files. Vanilla CSS in `styles.css`.
- **API client**: `frontend/src/api/client.js` — plain `fetch`, no HTTP libraries. SSE streaming uses `response.body.getReader()`.
- **Shared orchestration**: `core/orchestration.py` is the single source of truth for debate execution — both CLI and API call into it. Don't duplicate debate logic elsewhere.