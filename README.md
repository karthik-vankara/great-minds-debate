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
- **Session memory**: full chat history is carried across questions

## Project Structure

```
basics/
├── main.py           # Interactive CLI entry point
├── graph.py          # LangGraph StateGraph — all debate nodes
├── router.py         # LLM router with structured output
├── personas.py       # Agent definitions (system prompts, tags, colors)
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
