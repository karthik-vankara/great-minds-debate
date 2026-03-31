# AI Persona Debate Arena

An interactive LangGraph-powered debate system where an LLM router picks the two most relevant AI personas to debate any idea or question you throw at them.

## Personas

| Persona | Expertise |
|---|---|
| **Steve Jobs** | Product design, UX, simplicity, consumer tech, storytelling |
| **Elon Musk** | Space, EVs, AI, first-principles thinking, disruption |
| **Albert Einstein** | Physics, mathematics, thought experiments, philosophy of science |
| **Mark Zuckerberg** | Social media, metaverse, AR/VR, connectivity, data & scale |

## How It Works

```
User Question
     │
     ▼
 LLM Router (gpt-4o-mini)
 Picks 2 best-fit agents + confidence scores + reason
     │
     ▼
 Round 1 — Opening Statements  (both agents independently)
     │
     ▼
 Round 2 — Rebuttals           (each agent responds to the other)
     │
     ▼
 Round 3 — Closing Arguments   (each agent delivers their final word)
     │
     ▼
 Synthesis                     (neutral moderator summary)
```

- **Router model**: `gpt-4o-mini` (cheap, classification only)
- **Debate model**: `gpt-4.1` (quality persona responses)
- **Session memory**: recent conversation context is injected into routing and debate prompts

## Project Structure

```
basics/
├── app_state.py      # Runtime app state coordinator
├── cli_handlers.py   # Persona/session command handlers
├── debate_runner.py  # Debate orchestration + streaming output rendering
├── main.py           # Interactive CLI entry point
├── graph.py          # LangGraph StateGraph — all debate nodes
├── router.py         # LLM router with structured output
├── personas.py       # Persona definitions + JSON-backed custom persona repository
├── session_store.py  # JSON session persistence layer
├── state.py          # DebateState TypedDict
├── test.py           # Smoke test — verify setup before running
├── requirements.txt  # Python dependencies
└── .env              # Your API keys (not committed)
```

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your OpenAI API key

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

### 4. Verify setup

```bash
python test.py
```

Expected output:
```
[OK] OPENAI_API_KEY is set (sk-proj...)
[OK] All modules imported successfully.
[OK] Agents available: steve_jobs, elon_musk, einstein, zuckerberg

All checks passed. Run `python main.py` to start the debate arena.
```

## Running the App

```bash
python main.py
```

## Running The API (Phase 2)

You can now run the backend API for UI integration:

```bash
python3 -m uvicorn backend.main:app --reload
```

If you are using the project virtual environment directly:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Current API groups:

- `/api/debates` - run debates from non-CLI clients
- `/api/personas` - list/create/delete personas
- `/api/sessions` - list/save/load/delete sessions

## Running The UI (Phase 4)

The React + Vite frontend is in `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

Optional API base override:

```bash
VITE_API_BASE=http://127.0.0.1:8000/api npm run dev
```

You'll see the welcome banner and a prompt:

```
You: Should I quit my job and start a startup?
```

## Example Interaction

**Input:**
```
You: Is it worth going to Mars?
```

**Output (abbreviated):**
```
╭─ 🎯 ROUTER ──────────────────────────────────────────────╮
│ Agent 1: Elon Musk (97%)                                 │
│ Agent 2: Albert Einstein (74%)                           │
│ Reason: Space exploration + physics/science perspective  │
╰──────────────────────────────────────────────────────────╯

── Round 1 — Opening Statements ──────────────────────────

╭─ ELON MUSK — OPENING ────────────────────────────────────╮
│ Becoming multi-planetary is the most important thing     │
│ humanity can do right now. Earth is fragile...           │
╰──────────────────────────────────────────────────────────╯

╭─ ALBERT EINSTEIN — OPENING ──────────────────────────────╮
│ The question is not whether we can go, but whether we    │
│ have the wisdom to go for the right reasons...           │
╰──────────────────────────────────────────────────────────╯

── Round 2 — Rebuttals ────────────────────────────────────
...

── Round 3 — Closing Arguments ────────────────────────────
...

── Synthesis ──────────────────────────────────────────────

╭─ 🧠 MODERATOR SYNTHESIS ─────────────────────────────────╮
│ Musk and Einstein both agree Mars exploration is         │
│ technically achievable, but differ sharply on urgency... │
╰──────────────────────────────────────────────────────────╯
```

Type `quit` or `exit` to stop the session.

## Tips for Good Debates

- Ask about **technology ideas**: *"Should every app be social?"*
- Ask about **science/innovation**: *"Is quantum computing overhyped?"*
- Ask about **product/startup ideas**: *"I want to build an AI tutor — is this a good idea?"*
- Ask **philosophical questions**: *"Is simplicity always the right design goal?"*

The router automatically selects the two most relevant personas — you don't need to pick them.

## Dynamic Personas (New)

The app now supports custom personas with JSON persistence and two debate modes:

- `auto`: router picks the best two personas from the active pool
- `manual`: you pick the two personas directly for each debate

### CLI Commands

- `/personas` opens the persona manager (`list`, `add`, `edit`, `delete`, `back`)
- `/sessions` opens the session manager (`list`, `save`, `load`, `delete`, `back`)
- `/mode` switches between `auto` and `manual`
- `/help` shows command help

The CLI also shows the current runtime status before each prompt:

- active mode
- loaded session name
- current persona count

### Persona Storage

Custom personas are stored in:

```
.debate_arena/personas/custom_personas.json
```

Built-in personas remain immutable defaults. Custom personas are overlaid on top of built-ins.

Session history is stored in:

```
.debate_arena/sessions/
```

When a named session is loaded, each new debate turn auto-saves back to that session file.

### Future DB Extension

Persona persistence is implemented through a repository abstraction in `personas.py`.
This makes it straightforward to swap the JSON backend with a database backend later
without changing router/graph debate orchestration.
