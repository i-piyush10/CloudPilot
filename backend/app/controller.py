from __future__ import annotations

import math
import threading
from datetime import datetime, timedelta, timezone

from prometheus_client import Counter, Gauge

from .cluster import ClusterAdapter, ClusterError
from .config import Settings
from .predictor import LinearTrendPredictor
from .schemas import ControlDecision, ScalingMode, TelemetryIn
from .store import Store


DECISIONS = Counter("cloudpilot_scaling_decisions_total", "Scaling decisions", ["mode", "applied"])
CURRENT_REPLICAS = Gauge("cloudpilot_current_replicas", "Current replica count")
DESIRED_REPLICAS = Gauge("cloudpilot_desired_replicas", "Desired replica count")
PREDICTED_RPS = Gauge("cloudpilot_predicted_rps", "Predicted requests per second")
FORECAST_CONFIDENCE = Gauge("cloudpilot_forecast_confidence", "Forecast confidence from zero to one")
ACTIVE_ANOMALIES = Gauge("cloudpilot_active_anomalies", "Number of active anomaly conditions")
RECOVERIES = Counter("cloudpilot_recoveries_total", "Controlled recovery actions", ["action", "status"])


class Controller:
    def __init__(self, settings: Settings, store: Store, cluster: ClusterAdapter):
        self.settings = settings
        self.store = store
        self.cluster = cluster
        self.predictor = LinearTrendPredictor()
        self._last_scale_at: datetime | None = None
        self._last_recovery_at: datetime | None = None
        self._lock = threading.RLock()

    @property
    def mode(self) -> ScalingMode:
        return self.store.setting("scaling_mode", "fixed")  # type: ignore[return-value]

    def set_mode(self, mode: ScalingMode, fixed_replicas: int | None = None) -> None:
        with self._lock:
            self.cluster.ensure_hpa(mode == "hpa")
            self.store.set_setting("scaling_mode", mode)
            if fixed_replicas is not None:
                bounded = self._bounded(fixed_replicas)
                self.store.set_setting("fixed_replicas", str(bounded))
                if mode == "fixed":
                    self.cluster.scale(bounded)

    def _bounded(self, value: int) -> int:
        return max(self.settings.min_replicas, min(self.settings.max_replicas, value))

    def anomalies(self, sample: dict | None) -> list[str]:
        if not sample:
            return []
        found = []
        if float(sample["p95_latency_ms"]) >= 900:
            found.append("high_latency")
        if float(sample["error_rate"]) >= 0.08:
            found.append("high_error_rate")
        if int(sample["restart_count"]) >= 3:
            found.append("restart_loop")
        if float(sample["memory_mb"]) >= 700:
            found.append("high_memory")
        ACTIVE_ANOMALIES.set(len(found))
        return found

    def tick(self) -> ControlDecision:
        with self._lock:
            rows = self.store.telemetry(60)
            current = self.cluster.replicas()
            mode = self.mode
            forecast = self.predictor.predict(rows, self.settings.forecast_horizon_seconds)
            latest = rows[-1] if rows else None
            desired = current
            applied = False
            reason = "No replica change required"

            if mode == "fixed":
                desired = self._bounded(int(self.store.setting("fixed_replicas", str(current))))
                reason = "Fixed mode maintains the configured replica count"
            elif mode == "hpa":
                desired = current
                reason = "Kubernetes HPA owns replica decisions in this mode"
            elif forecast.sample_count < self.predictor.minimum_samples:
                reason = f"Collecting telemetry: {forecast.sample_count}/{self.predictor.minimum_samples} samples"
            elif forecast.confidence < 0.35:
                reason = f"Forecast confidence {forecast.confidence:.2f} is below the safety threshold"
            else:
                desired = self._bounded(
                    math.ceil(forecast.predicted_rps * self.settings.headroom / self.settings.capacity_rps_per_pod)
                )
                reason = (
                    f"Forecast {forecast.predicted_rps:.1f} rps at {forecast.confidence:.0%} confidence; "
                    f"capacity target {self.settings.capacity_rps_per_pod:.1f} rps/pod"
                )

            now = datetime.now(timezone.utc)
            cooled_down = self._last_scale_at is None or now - self._last_scale_at >= timedelta(
                seconds=self.settings.scale_cooldown_seconds
            )
            if mode != "hpa" and desired != current and cooled_down:
                self.cluster.scale(desired)
                current_after = desired
                applied = True
                self._last_scale_at = now
            else:
                current_after = current
                if desired != current and not cooled_down:
                    reason += "; held by scaling cooldown"

            if latest:
                self._recover_if_needed(self.anomalies(latest), now)

            decision = ControlDecision(
                timestamp=now,
                mode=mode,
                current_replicas=current,
                desired_replicas=desired,
                predicted_rps=forecast.predicted_rps,
                confidence=forecast.confidence,
                reason=reason,
                applied=applied,
            )
            self.store.add_decision(decision.model_dump(mode="json"))
            DECISIONS.labels(mode, str(applied).lower()).inc()
            CURRENT_REPLICAS.set(current_after)
            DESIRED_REPLICAS.set(desired)
            PREDICTED_RPS.set(forecast.predicted_rps)
            FORECAST_CONFIDENCE.set(forecast.confidence)
            return decision

    def _recover_if_needed(self, anomalies: list[str], now: datetime) -> None:
        severe = {"high_error_rate", "restart_loop"}.intersection(anomalies)
        if not severe:
            return
        if self._last_recovery_at and now - self._last_recovery_at < timedelta(minutes=3):
            return
        action = "rollout_restart"
        try:
            self.cluster.restart()
            status = "applied"
            detail = f"Detected {', '.join(sorted(severe))}; performed allow-listed rollout restart"
            self._last_recovery_at = now
        except ClusterError as exc:
            status = "failed"
            detail = str(exc)
        self.store.add_incident(";".join(sorted(severe)), "high", action, status, detail)
        RECOVERIES.labels(action, status).inc()

