# Maestro

**A live multi-agent orchestration studio. Give it a goal and watch a team of AI agents plan, research, critique, and deliver in real time.**

[![CI](https://github.com/SaadAsif-NU/maestro/actions/workflows/ci.yml/badge.svg)](https://github.com/SaadAsif-NU/maestro/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.13-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

![Maestro mission control](docs/maestro.png)

Maestro turns a one-line goal into a coordinated run across a team of specialised agents (a planner, parallel researchers, an analyst, a critic, and a writer) and renders the whole thing as a live mission-control dashboard: an animated agent graph, streaming thoughts, tool calls, running cost and latency, and a final deliverable.

It is a demonstration of how to build and, just as importantly, how to *observe* an autonomous multi-agent system: a real async orchestration engine, an event-sourced pub/sub bus, and a WebSocket UI that is a pure projection of the event stream.

> **Runs anywhere, instantly.** Maestro ships with a deterministic offline brain, so the studio boots and runs a full multi-agent workflow with no API key and no network. Drop in an `OPENAI_API_KEY` to swap the offline brain for a real model. The orchestration is identical either way.

---

## Highlights

- 🎛️ **Live mission control.** An animated agent graph where nodes light up as they think, edges pulse as work is handed off, and thoughts stream in token by token, alongside live token, tool-call, throughput, and latency metrics.
- 🕹️ **Interactive.** Size the team (1 to 4 researchers), click any agent to inspect its full reasoning and tool calls, stop a run in flight, replay past runs from the history strip, and copy or download the final deliverable.
- 🧠 **Real orchestration engine.** A recognisable multi-agent pattern (plan, fan out parallel research, synthesise, critique, write) built on async Python.
- 🔭 **Event-sourced and observable.** Every action is an event on a per-run bus. The UI, a reconnecting client, run replay, and the tests are all projections of the same ordered, replayable stream.
- 🔌 **Pluggable brains and tools.** Runs offline out of the box; add a free Gemini key (or OpenAI, or any OpenAI-compatible endpoint) for real models. Add tools without touching the agents.
- 🌐 **Build-free frontend.** The UI is served by the backend as static files. No Node toolchain, no bundler. `pip install` and it runs.
- ✅ **Tested and typed.** Async `pytest` across the stack, `mypy`-clean, `ruff`-clean, CI on Python 3.10 to 3.13.

Click any agent to open the inspector and read its full reasoning and tool calls:

![Agent inspector](docs/maestro-inspector.png)

## How it works

A run is a fixed, observable pipeline. Each stage streams its work through the event bus.

```
                     ┌──────────────┐
     goal  ─────────▶│ Orchestrator │  plans and assigns workstreams
                     └──────┬───────┘
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐   (parallel research, each with a
        │Researcher│  │Researcher│    knowledge-base search tool)
        └─────┬────┘  └────┬─────┘
              └──────┬──────┘
                     ▼
                ┌─────────┐   synthesises findings, cross-checks a
                │ Analyst │   figure with the calculator
                └────┬────┘
                     ▼
                ┌─────────┐   pressure-tests the analysis
                │ Critic  │
                └────┬────┘
                     ▼
                ┌─────────┐   composes the final deliverable
                │ Writer  │
                └─────────┘
```

The **engine** starts each run as a background task with its own **event bus**. The **server** exposes that bus over a WebSocket; the browser renders it. Because the bus is event-sourced (it keeps the full ordered log), a client that connects late or reconnects replays the run with no gap and no duplicate.

## Architecture

| Layer | Responsibility |
|---|---|
| `events` | The `Event` model and a replayable async `EventBus` (per-run pub/sub). |
| `brains` | The `Brain` interface, a deterministic offline `SimulatedBrain`, and one adapter for any OpenAI-compatible API. That single adapter (`brains/openai.py`) serves both OpenAI and Google Gemini, since Gemini exposes an OpenAI-compatible endpoint. |
| `tools` | The `Tool` interface plus an offline knowledge-base `SearchTool` and a safe `CalculatorTool`. |
| `agents` | An `Agent` that streams reasoning, calls tools, and emits an event for everything it does. |
| `orchestrator` | Coordinates the ensemble: plan, parallel research, synthesise, critique, write. |
| `engine` | Run lifecycle: background execution, status, and event subscription. |
| `server` | FastAPI + WebSocket API, and the static mission-control UI. |

The dependency direction is strict and one-way. The orchestrator depends on the `Brain` and `Tool` *interfaces*, never on concrete implementations, so the offline brain and a real model are perfectly interchangeable.

## Getting started

**Step 1. Prerequisites.** Python 3.10 or newer.

**Step 2. Get the code and install it.**

```bash
git clone https://github.com/SaadAsif-NU/maestro.git
cd maestro
python3 -m venv .venv
source .venv/bin/activate           # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Step 3. Run it (offline, no key needed).**

```bash
maestro serve
```

Open **http://localhost:8000**, type a goal (or click an example), pick the team size, and press **Run**. Everything runs on the built-in offline brain, so no key and no internet are required.

- Stop the server with `Ctrl+C`.
- Use a different port with `maestro serve --port 8080`.
- If `maestro serve` is not found (some shells or a project path with spaces), use the equivalent: `python -m uvicorn maestro.server.app:app --port 8000`.
- Prefer the terminal? `maestro run "Design a launch plan for a new product"` prints the deliverable.

## Using a real model (Gemini or OpenAI)

The studio runs offline by default. To use a real model, provide an API key. There are two ways; the active model always shows in the brain badge.

### Option A: a `.env` file (recommended, no terminal exports)

```bash
cp .env.example .env
# open .env and paste your key, then:
maestro serve
```

Get a **free Gemini key** at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Maestro loads `.env` automatically on startup, and `.env` is gitignored so your key never gets committed. To change the model later, edit `.env` and restart.

### Option B: environment variables (per shell session)

```bash
export GEMINI_API_KEY=your-key
export MAESTRO_MODEL=gemini-2.0-flash    # optional
maestro serve
```

For OpenAI, set `OPENAI_API_KEY` instead. Point `OPENAI_BASE_URL` or `GEMINI_BASE_URL` at vLLM, Together, Groq, or a local server.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `429 Too Many Requests` | A free-tier per-minute limit from the parallel fan-out. Maestro auto-retries with backoff; you can also lower `MAESTRO_MAX_CONCURRENCY` (to `1`), reduce the researcher count in the UI, or wait about a minute. |
| `503 Service Unavailable` | A transient error on the provider's side. Maestro retries it automatically; if it persists, wait and run again. |
| Port already in use | Start on another port: `maestro serve --port 8080`. |
| Want a guaranteed-smooth demo | Leave the key blank (or `unset GEMINI_API_KEY`) to run on the offline brain: instant, unlimited, no network. |

## Extending

- **New tool** (web search, a vector store, code execution): implement the `Tool` interface and add it to the toolbox. Agents pick it up unchanged.
- **New brain** (Anthropic, Bedrock, a local model): implement the `Brain` streaming interface.
- **New role or topology**: the orchestrator is plain async Python; add an agent and wire its edges.

## Development

```bash
make dev        # install with dev deps
make test       # run the async test suite
make cov        # tests + coverage
make lint       # ruff
make typecheck  # mypy
make serve      # run the studio locally
```

## The deliverable

When the run finishes, the studio renders the writer's output as a clean, structured document.

![Deliverable](docs/maestro-deliverable.png)

## License

[MIT](LICENSE) © Saad Asif
