from datetime import datetime, timedelta, timezone

from app.cluster import SimulatedCluster
from app.config import Settings
from app.controller import Controller
from app.schemas import TelemetryIn
from app.store import Store


def make_controller():
    settings = Settings(
        mode="simulation",
        database=":memory:",
        min_replicas=1,
        max_replicas=5,
        capacity_rps_per_pod=20,
        headroom=1.2,
        forecast_horizon_seconds=30,
        scale_cooldown_seconds=0,
    )
    store = Store(":memory:")
    cluster = SimulatedCluster(1)
    return Controller(settings, store, cluster), store, cluster


def add_samples(store, values):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index, value in enumerate(values):
        store.add_telemetry(
            TelemetryIn(
                timestamp=start + timedelta(seconds=15 * index),
                request_rate=value,
                cpu_percent=50,
                memory_mb=120,
                p95_latency_ms=100,
                error_rate=0,
            )
        )


def test_predictive_mode_scales_within_bounds():
    controller, store, cluster = make_controller()
    add_samples(store, [30, 40, 50, 60, 70, 80])
    controller.set_mode("predictive")
    decision = controller.tick()
    assert decision.applied is True
    assert decision.desired_replicas == 5
    assert cluster.replicas() == 5


def test_hpa_mode_does_not_write_replicas():
    controller, store, cluster = make_controller()
    add_samples(store, [30, 40, 50, 60, 70])
    controller.set_mode("hpa")
    decision = controller.tick()
    assert decision.applied is False
    assert cluster.replicas() == 1


def test_anomaly_detection_is_bounded_to_known_rules():
    controller, _, _ = make_controller()
    anomalies = controller.anomalies(
        {"p95_latency_ms": 950, "error_rate": 0.1, "restart_count": 0, "memory_mb": 100}
    )
    assert set(anomalies) == {"high_latency", "high_error_rate"}

