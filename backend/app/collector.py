from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .schemas import TelemetryIn


class PrometheusCollector:
    def __init__(self, base_url: str, timeout: float = 2.5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(self, expression: str, default: float = 0.0) -> float:
        url = f"{self.base_url}/api/v1/query?{urllib.parse.urlencode({'query': expression})}"
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            payload = json.load(response)
        results = payload.get("data", {}).get("result", [])
        if not results:
            return default
        raw = results[0].get("value", [None, default])[1]
        try:
            value = float(raw)
            return default if value != value else value
        except (TypeError, ValueError):
            return default

    def collect(self) -> TelemetryIn:
        request_rate = self.query('sum(rate(workload_http_requests_total{endpoint="work"}[1m]))')
        p95_latency_ms = 1000 * self.query(
            'histogram_quantile(0.95, sum(rate(workload_http_request_duration_seconds_bucket{endpoint="work"}[5m])) by (le))'
        )
        error_rate = self.query(
            'sum(rate(workload_http_requests_total{endpoint="work",status=~"5.."}[1m])) '
            '/ clamp_min(sum(rate(workload_http_requests_total{endpoint="work"}[1m])), 0.001)'
        )
        cpu_percent = 100 * self.query('sum(rate(process_cpu_seconds_total{job="workload"}[1m]))')
        memory_mb = self.query('sum(process_resident_memory_bytes{job="workload"}) / 1024 / 1024')
        return TelemetryIn(
            timestamp=datetime.now(timezone.utc),
            request_rate=max(0, request_rate),
            cpu_percent=max(0, min(100, cpu_percent)),
            memory_mb=max(0, memory_mb),
            p95_latency_ms=max(0, p95_latency_ms),
            error_rate=max(0, min(1, error_rate)),
            restart_count=0,
        )
