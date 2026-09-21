from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ScalingMode = Literal["fixed", "hpa", "predictive"]


class TelemetryIn(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_rate: float = Field(ge=0)
    cpu_percent: float = Field(ge=0, le=100)
    memory_mb: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    error_rate: float = Field(ge=0, le=1)
    restart_count: int = Field(default=0, ge=0)


class ModeUpdate(BaseModel):
    mode: ScalingMode
    fixed_replicas: int | None = Field(default=None, ge=1, le=50)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    scenario: Literal["constant", "ramp", "spike", "periodic", "failure"]
    mode: ScalingMode
    duration_seconds: int = Field(default=300, ge=30, le=7200)


class ControlDecision(BaseModel):
    timestamp: datetime
    mode: ScalingMode
    current_replicas: int
    desired_replicas: int
    predicted_rps: float
    confidence: float
    reason: str
    applied: bool


class StatusResponse(BaseModel):
    service: str
    cluster_mode: str
    scaling_mode: ScalingMode
    current_replicas: int
    desired_replicas: int
    workload_healthy: bool
    latest: TelemetryIn | None
    latest_decision: ControlDecision | None
    active_anomalies: list[str]

