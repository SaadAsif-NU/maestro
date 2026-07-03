"""Typed request/response models for the HTTP API.

Keeping these explicit gives the endpoints a real OpenAPI contract (visible at
``/docs``) instead of returning bare dicts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    brain: str


class ProviderInfo(BaseModel):
    id: str
    label: str
    configured: bool
    models: list[str]


class Selection(BaseModel):
    provider: str
    model: str


class ConfigResponse(BaseModel):
    providers: list[ProviderInfo]
    default: Selection


class RunStartedResponse(BaseModel):
    run_id: str
    brain: str


class RunListItem(BaseModel):
    run_id: str
    goal: str
    status: str


class RunListResponse(BaseModel):
    runs: list[RunListItem]


class RunInfoResponse(BaseModel):
    run_id: str
    goal: str
    status: str
    summary: dict[str, Any] | None = None


class StatusResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str
