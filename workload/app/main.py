from __future__ import annotations

import hashlib
import math
import os
import time

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .telemetry import configure_tracing


app = FastAPI(title="CloudPilot Sample Workload", version="1.0.0")
configure_tracing(app, "cloudpilot-workload")

REQUESTS = Counter("workload_http_requests_total", "Requests handled by the sample workload", ["endpoint", "status"])
LATENCY = Histogram(
    "workload_http_request_duration_seconds",
    "Request duration for the sample workload",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
IN_FLIGHT = Gauge("workload_in_flight_requests", "Currently executing workload requests")
FAULT_MODE = Gauge("workload_fault_mode", "Whether a controlled fault mode is active", ["kind"])


def cpu_work(iterations: int) -> str:
    value = b"cloudpilot"
    for _ in range(iterations):
        value = hashlib.sha256(value).digest()
    return value.hex()[:12]


@app.get("/healthz")
def healthz() -> dict:
    REQUESTS.labels("healthz", "200").inc()
    return {"status": "ok", "pod": os.getenv("HOSTNAME", "local")}


@app.get("/api/work")
def work(
    iterations: int = Query(default=8_000, ge=100, le=200_000),
    delay_ms: int = Query(default=0, ge=0, le=3_000),
    fail: bool = False,
) -> dict:
    endpoint = "work"
    started = time.perf_counter()
    IN_FLIGHT.inc()
    try:
        if delay_ms:
            time.sleep(delay_ms / 1000)
        digest = cpu_work(iterations)
        if fail:
            REQUESTS.labels(endpoint, "503").inc()
            raise HTTPException(status_code=503, detail="Controlled demo failure")
        REQUESTS.labels(endpoint, "200").inc()
        return {
            "result": digest,
            "iterations": iterations,
            "delay_ms": delay_ms,
            "pod": os.getenv("HOSTNAME", "local"),
        }
    finally:
        LATENCY.labels(endpoint).observe(time.perf_counter() - started)
        IN_FLIGHT.dec()


@app.get("/api/fault/{kind}")
def fault(kind: str) -> dict:
    if kind not in {"latency", "errors", "cpu"}:
        raise HTTPException(status_code=400, detail="Unsupported controlled fault")
    FAULT_MODE.labels(kind).set(1)
    if kind == "latency":
        time.sleep(1.0)
    elif kind == "cpu":
        cpu_work(150_000)
    elif kind == "errors":
        REQUESTS.labels("fault", "503").inc()
        FAULT_MODE.labels(kind).set(0)
        raise HTTPException(status_code=503, detail="Controlled error fault")
    REQUESTS.labels("fault", "200").inc()
    FAULT_MODE.labels(kind).set(0)
    return {"fault": kind, "status": "completed"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
