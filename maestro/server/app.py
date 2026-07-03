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
from ..brains import build_brain
from ..engine import Engine
from ..types import RunRequest

_STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Maestro", version=__version__, summary="A live multi-agent orchestration studio."
)
engine = Engine()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "brain": build_brain().name}


@app.post("/api/runs")
async def start_run(body: RunRequest) -> dict[str, str]:
    handle = engine.start_run(body.goal, researchers=body.researchers)
    return {"run_id": handle.run_id, "brain": build_brain().name}


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
