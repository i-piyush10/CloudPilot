from __future__ import annotations

import asyncio
import statistics
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from .cluster import ClusterError, create_cluster
from .collector import PrometheusCollector
from .config import Settings
from .controller import Controller
from .schemas import ExperimentCreate, ModeUpdate, StatusResponse, TelemetryIn
from .store import Store
from .telemetry import configure_tracing


settings = Settings()
settings.validate()
store = Store(settings.database)
cluster = create_cluster(settings)
controller = Controller(settings, store, cluster)
collector = PrometheusCollector(settings.prometheus_url)

TELEMETRY_SAMPLES = Counter("cloudpilot_telemetry_samples_total", "Ingested telemetry samples")
REQUEST_RATE = Gauge("cloudpilot_observed_request_rate", "Observed requests per second")
P95_LATENCY = Gauge("cloudpilot_observed_p95_latency_ms", "Observed p95 latency in milliseconds")
ERROR_RATE = Gauge("cloudpilot_observed_error_rate", "Observed request error ratio")


async def control_loop() -> None:
    while True:
        try:
            sample = await asyncio.to_thread(collector.collect)
            store.add_telemetry(sample)
            TELEMETRY_SAMPLES.inc()
            REQUEST_RATE.set(sample.request_rate)
            P95_LATENCY.set(sample.p95_latency_ms)
            ERROR_RATE.set(sample.error_rate)
            controller.tick()
        except Exception as exc:  # Prometheus may still be starting; manual telemetry remains available.
            if "Connection refused" not in str(exc) and "timed out" not in str(exc):
                store.add_incident("control_loop", "medium", "none", "failed", str(exc))
        await asyncio.sleep(settings.control_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(control_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="CloudPilot Control Plane",
    version="1.0.0",
    description="Local-first predictive autoscaling and controlled self-healing prototype.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
configure_tracing(app, "cloudpilot-control-plane")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/telemetry", status_code=202)
def ingest(sample: TelemetryIn) -> dict:
    store.add_telemetry(sample)
    TELEMETRY_SAMPLES.inc()
    REQUEST_RATE.set(sample.request_rate)
    P95_LATENCY.set(sample.p95_latency_ms)
    ERROR_RATE.set(sample.error_rate)
    return {"accepted": True}


@app.get("/api/status", response_model=StatusResponse)
def status() -> StatusResponse:
    latest_row = store.latest_telemetry()
    decisions = store.decisions(1)
    try:
        replicas = cluster.replicas()
    except ClusterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    latest = TelemetryIn.model_validate(latest_row) if latest_row else None
    latest_decision = decisions[0] if decisions else None
    desired = int(latest_decision["desired_replicas"]) if latest_decision else replicas
    anomalies = controller.anomalies(latest_row)
    return StatusResponse(
        service="CloudPilot",
        cluster_mode=settings.mode,
        scaling_mode=controller.mode,
        current_replicas=replicas,
        desired_replicas=desired,
        workload_healthy=not {"high_error_rate", "restart_loop"}.intersection(anomalies),
        latest=latest,
        latest_decision=latest_decision,
        active_anomalies=anomalies,
    )


@app.get("/api/timeseries")
def timeseries(limit: int = Query(default=120, ge=1, le=1000)) -> dict:
    return {"items": store.telemetry(limit)}


@app.get("/api/decisions")
def decisions(limit: int = Query(default=30, ge=1, le=200)) -> dict:
    return {"items": store.decisions(limit)}


@app.get("/api/incidents")
def incidents(limit: int = Query(default=30, ge=1, le=200)) -> dict:
    return {"items": store.incidents(limit)}


@app.post("/api/mode")
def update_mode(update: ModeUpdate) -> dict:
    if update.mode == "fixed" and update.fixed_replicas is None:
        raise HTTPException(status_code=422, detail="fixed_replicas is required in fixed mode")
    try:
        controller.set_mode(update.mode, update.fixed_replicas)
    except ClusterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": controller.mode, "fixed_replicas": update.fixed_replicas}


@app.post("/api/control/tick")
def tick() -> dict:
    try:
        return controller.tick().model_dump(mode="json")
    except ClusterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/experiments", status_code=201)
def create_experiment(experiment: ExperimentCreate) -> dict:
    experiment_id = store.add_experiment(experiment)
    return {"id": experiment_id, "status": "planned"}


@app.get("/api/experiments")
def experiments() -> dict:
    return {"items": store.experiments()}


@app.post("/api/experiments/{experiment_id}/start")
def start_experiment(experiment_id: int) -> dict:
    experiment = store.experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment["status"] not in {"planned", "completed"}:
        raise HTTPException(status_code=409, detail="Experiment is already running")
    try:
        controller.set_mode(experiment["mode"])
    except ClusterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.set_experiment_status(experiment_id, "running", {})
    return {"id": experiment_id, "status": "running", "mode": experiment["mode"]}


@app.post("/api/experiments/{experiment_id}/complete")
def complete_experiment(experiment_id: int) -> dict:
    experiment = store.experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    samples = store.telemetry_since(experiment["created_at"])
    decisions_after_start = store.decisions_since(experiment["created_at"])
    if not samples:
        raise HTTPException(status_code=409, detail="No telemetry was collected during this experiment")
    latencies = [float(item["p95_latency_ms"]) for item in samples]
    errors = [float(item["error_rate"]) for item in samples]
    request_rates = [float(item["request_rate"]) for item in samples]
    result = {
        "sample_count": len(samples),
        "mean_request_rate_rps": round(statistics.fmean(request_rates), 3),
        "mean_p95_latency_ms": round(statistics.fmean(latencies), 3),
        "max_p95_latency_ms": round(max(latencies), 3),
        "mean_error_rate": round(statistics.fmean(errors), 5),
        "scaling_actions": sum(1 for item in decisions_after_start if item["applied"]),
        "decision_count": len(decisions_after_start),
    }
    store.set_experiment_status(experiment_id, "completed", result)
    return {"id": experiment_id, "status": "completed", "result": result}


@app.post("/api/faults/{kind}")
def inject_fault(kind: str) -> dict:
    allowed = {"latency", "errors", "pod_restart"}
    if kind not in allowed:
        raise HTTPException(status_code=400, detail=f"fault must be one of {sorted(allowed)}")
    try:
        if kind == "pod_restart":
            cluster.restart()
            detail = "Applied an allow-listed rollout restart to the sample workload"
        else:
            request = urllib.request.Request(f"{settings.workload_url}/api/fault/{kind}", method="GET")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    response.read()
            except urllib.error.HTTPError as exc:
                if not (kind == "errors" and exc.code == 503):
                    raise
            detail = f"Executed the controlled {kind} fault in the sample workload"
        status_value = "completed"
    except (ClusterError, urllib.error.URLError, OSError) as exc:
        status_value = "failed"
        detail = f"Controlled fault could not be executed: {exc}"
    incident_id = store.add_incident(kind, "medium", "demo_injection", status_value, detail)
    if status_value == "failed":
        raise HTTPException(status_code=503, detail=detail)
    return {"incident_id": incident_id, "kind": kind, "status": status_value}
