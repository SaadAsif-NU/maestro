"""FastAPI + WebSocket server for the studio.

Endpoints:
    POST /api/runs                start a run, returns its id and brain
    GET  /api/runs                list this session's runs (history)
    POST /api/runs/{id}/cancel    stop a running run
    WS   /api/runs/{id}/events    stream the run's events (with replay)
    GET  /api/runs/{id}           run status and summary
    GET  /api/config              providers, models, and key status
    GET  /health                  liveness
    GET  /                        the mission-control UI

The WebSocket is a thin projection of the engine's event bus, so a client that
connects late or reconnects still receives the full run.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..brains import build_brain, default_selection, provider_models, provider_status
from ..config import Settings
from ..engine import Engine, EngineBusyError
from ..env import load_env
from ..observability import configure_logging, log_event
from ..types import RunRequest
from .schemas import (
    ConfigResponse,
    ErrorResponse,
    HealthResponse,
    ProviderInfo,
    RunInfoResponse,
    RunListItem,
    RunListResponse,
    RunStartedResponse,
    Selection,
    StatusResponse,
)

_PROVIDER_LABELS = {
    "simulated": "Offline (no key needed)",
    "gemini": "Google Gemini",
    "openai": "OpenAI",
}

# Load a .env before reading settings, then configure logging. Try the current
# working directory first (the usual case) and then the project root next to the
# package, so the server finds the key no matter which directory it is launched
# from (uvicorn, `maestro serve`, an IDE, ...).
load_env()
load_env(Path(__file__).resolve().parents[2] / ".env")
settings = Settings.from_env()
configure_logging(settings.log_level)

_STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Maestro",
    version=__version__,
    summary="A live multi-agent orchestration studio.",
)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
engine = Engine(settings=settings)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    _, model = default_selection()
    return HealthResponse(status="ok", version=__version__, brain=model)


@app.get("/api/config", response_model=ConfigResponse, tags=["meta"])
async def config() -> ConfigResponse:
    """Which providers/models are available and whether each key is configured."""
    status = provider_status()
    default_provider, default_model = default_selection()
    providers = [
        ProviderInfo(
            id=pid,
            label=_PROVIDER_LABELS.get(pid, pid),
            configured=status[pid],
            models=provider_models(pid),
        )
        for pid in ("simulated", "gemini", "openai")
    ]
    return ConfigResponse(
        providers=providers, default=Selection(provider=default_provider, model=default_model)
    )


@app.post(
    "/api/runs",
    response_model=RunStartedResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["runs"],
)
async def start_run(body: RunRequest) -> RunStartedResponse | JSONResponse:
    provider, model = body.provider, body.model
    if provider in ("gemini", "openai") and not provider_status().get(provider, False):
        env = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
        return JSONResponse(
            status_code=400,
            content={"error": f"{provider} is not configured; set {env} (or use offline)."},
        )
    try:
        handle = engine.start_run(
            body.goal,
            researchers=body.researchers,
            brain_factory=(lambda: build_brain(provider, model)) if provider else None,
        )
    except EngineBusyError:
        return JSONResponse(
            status_code=503, content={"error": "the studio is busy; try again shortly."}
        )
    label = model if (provider and provider != "simulated" and model) else default_selection()[1]
    return RunStartedResponse(run_id=handle.run_id, brain=label)


@app.get("/api/runs", response_model=RunListResponse, tags=["runs"])
async def list_runs() -> RunListResponse:
    return RunListResponse(runs=[RunListItem(**r) for r in engine.list_runs()])


@app.post(
    "/api/runs/{run_id}/cancel",
    response_model=StatusResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["runs"],
)
async def cancel_run(run_id: str) -> StatusResponse | JSONResponse:
    if engine.get(run_id) is None:
        return JSONResponse(status_code=404, content={"error": "run not found"})
    cancelled = engine.cancel(run_id)
    return StatusResponse(status="cancelled" if cancelled else "not_running")


@app.get(
    "/api/runs/{run_id}",
    response_model=RunInfoResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["runs"],
)
async def get_run(run_id: str) -> RunInfoResponse | JSONResponse:
    handle = engine.get(run_id)
    if handle is None:
        return JSONResponse(status_code=404, content={"error": "run not found"})
    return RunInfoResponse(
        run_id=handle.run_id,
        goal=handle.goal,
        status=handle.status.value,
        summary=handle.summary.model_dump() if handle.summary else None,
    )


@app.websocket("/api/runs/{run_id}/events")
async def stream_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    if engine.get(run_id) is None:
        await websocket.send_json({"type": "error", "data": {"message": "run not found"}})
        await websocket.close()
        return
    log_event("ws.connected", run_id=run_id)
    try:
        async for event in engine.subscribe(run_id):
            await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        return
    finally:
        # The bus has closed (run finished) or the client left; close cleanly.
        with contextlib.suppress(RuntimeError):
            await websocket.close()


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


# Static assets (styles.css, app.js). Mounted last so it does not shadow the API.
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
