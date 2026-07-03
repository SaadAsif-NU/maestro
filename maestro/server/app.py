"""FastAPI + WebSocket server for the studio.

Endpoints:
    POST /api/runs                start a run, returns its id and brain
    WS   /api/runs/{id}/events    stream the run's events (with replay)
    GET  /api/runs/{id}           run status and summary
    GET  /health                  liveness
    GET  /                        the mission-control UI

The WebSocket is a thin projection of the engine's event bus, so a client that
connects late or reconnects still receives the full run.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..brains import build_brain, default_selection, provider_models, provider_status
from ..engine import Engine
from ..env import load_env
from ..types import RunRequest

_PROVIDER_LABELS = {
    "simulated": "Offline (no key needed)",
    "gemini": "Google Gemini",
    "openai": "OpenAI",
}

# Pick up keys/config from a .env file if present, so users need not export
# environment variables in the shell.
load_env()

_STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Maestro", version=__version__, summary="A live multi-agent orchestration studio."
)
engine = Engine()


@app.get("/health")
async def health() -> dict[str, str]:
    provider, model = default_selection()
    return {"status": "ok", "version": __version__, "brain": model}


@app.get("/api/config")
async def config() -> dict[str, object]:
    """Which providers/models are available and whether each key is configured."""
    status = provider_status()
    default_provider, default_model = default_selection()
    providers = [
        {
            "id": pid,
            "label": _PROVIDER_LABELS.get(pid, pid),
            "configured": status[pid],
            "models": provider_models(pid),
        }
        for pid in ("simulated", "gemini", "openai")
    ]
    return {"providers": providers, "default": {"provider": default_provider, "model": default_model}}


@app.post("/api/runs")
async def start_run(body: RunRequest) -> JSONResponse:
    provider = body.provider
    model = body.model
    if provider in ("gemini", "openai") and not provider_status().get(provider, False):
        env = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
        return JSONResponse(
            status_code=400,
            content={"error": f"{provider} is not configured; set {env} (or use offline)."},
        )
    handle = engine.start_run(
        body.goal,
        researchers=body.researchers,
        brain_factory=(lambda: build_brain(provider, model)) if provider else None,
    )
    label = model if provider and provider != "simulated" else default_selection()[1]
    return JSONResponse({"run_id": handle.run_id, "brain": label})


@app.get("/api/runs")
async def list_runs() -> dict[str, list[dict[str, str]]]:
    return {"runs": engine.list_runs()}


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> JSONResponse:
    if engine.get(run_id) is None:
        return JSONResponse(status_code=404, content={"error": "run not found"})
    cancelled = engine.cancel(run_id)
    return JSONResponse({"status": "cancelled" if cancelled else "not_running"})


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    handle = engine.get(run_id)
    if handle is None:
        return JSONResponse(status_code=404, content={"error": "run not found"})
    return JSONResponse(
        {
            "run_id": handle.run_id,
            "goal": handle.goal,
            "status": handle.status.value,
            "summary": handle.summary.model_dump() if handle.summary else None,
        }
    )


@app.websocket("/api/runs/{run_id}/events")
async def stream_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    if engine.get(run_id) is None:
        await websocket.send_json({"type": "error", "data": {"message": "run not found"}})
        await websocket.close()
        return
    try:
        async for event in engine.subscribe(run_id):
            await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        return
    finally:
        # The bus has closed (run finished) or the client left; close cleanly.
        with contextlib.suppress(RuntimeError):
            await websocket.close()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


# Static assets (styles.css, app.js). Mounted last so it does not shadow the API.
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def _configure() -> None:
    os.environ.setdefault("MAESTRO_LOG_LEVEL", "INFO")


_configure()
