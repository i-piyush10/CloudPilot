from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("CLOUDPILOT_MODE", "simulation")
    database: str = os.getenv("CLOUDPILOT_DATABASE", "./cloudpilot.db")
    workload_url: str = os.getenv("CLOUDPILOT_WORKLOAD_URL", "http://localhost:8001")
    prometheus_url: str = os.getenv("CLOUDPILOT_PROMETHEUS_URL", "http://localhost:9090")
    min_replicas: int = _int("CLOUDPILOT_MIN_REPLICAS", 1)
    max_replicas: int = _int("CLOUDPILOT_MAX_REPLICAS", 8)
    capacity_rps_per_pod: float = _float("CLOUDPILOT_CAPACITY_RPS_PER_POD", 20.0)
    headroom: float = _float("CLOUDPILOT_HEADROOM", 1.25)
    forecast_horizon_seconds: int = _int("CLOUDPILOT_FORECAST_HORIZON_SECONDS", 60)
    control_interval_seconds: int = _int("CLOUDPILOT_CONTROL_INTERVAL_SECONDS", 15)
    scale_cooldown_seconds: int = _int("CLOUDPILOT_SCALE_COOLDOWN_SECONDS", 45)
    namespace: str = os.getenv("CLOUDPILOT_NAMESPACE", "cloudpilot")
    deployment: str = os.getenv("CLOUDPILOT_DEPLOYMENT", "cloudpilot-workload")
    label_selector: str = os.getenv("CLOUDPILOT_LABEL_SELECTOR", "app=cloudpilot-workload")
    allowed_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv(
            "CLOUDPILOT_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080"
        ).split(",")
        if value.strip()
    )

    def validate(self) -> None:
        if self.mode not in {"simulation", "kubernetes"}:
            raise ValueError("CLOUDPILOT_MODE must be simulation or kubernetes")
        if not 1 <= self.min_replicas <= self.max_replicas:
            raise ValueError("replica bounds are invalid")
        if self.capacity_rps_per_pod <= 0 or self.headroom < 1:
            raise ValueError("capacity must be positive and headroom must be >= 1")
