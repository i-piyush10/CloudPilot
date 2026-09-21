#!/usr/bin/env python3
"""Stream deterministic, realistic demo telemetry into a running CloudPilot API."""

from __future__ import annotations

import argparse
import json
import math
import random
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


running = True


def stop_stream(*_: object) -> None:
    global running
    running = False


def request(base_url: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def workload(index: int, scenario: str) -> float:
    phase = index % 90
    if scenario == "ramp":
        return 8 + phase * 1.05
    if scenario == "periodic":
        return 42 + 30 * math.sin(index / 7)
    if scenario == "constant":
        return 32
    # A repeating warm-up, sudden spike, recovery, and quiet period.
    if phase < 20:
        return 12 + phase * 0.6
    if phase < 45:
        return 85 + (phase - 20) * 1.2
    if phase < 65:
        return 65 - (phase - 45) * 2.2
    return 18


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate CloudPilot with live demo telemetry")
    parser.add_argument("--api", default="http://127.0.0.1:18000")
    parser.add_argument("--scenario", choices=("spike", "ramp", "periodic", "constant"), default="spike")
    parser.add_argument("--mode", choices=("fixed", "hpa", "predictive"), default="predictive")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--samples", type=int, default=0, help="0 streams until Ctrl+C")
    args = parser.parse_args()

    randomizer = random.Random(42)
    signal.signal(signal.SIGINT, stop_stream)
    signal.signal(signal.SIGTERM, stop_stream)
    mode_payload = {"mode": args.mode}
    if args.mode == "fixed":
        mode_payload["fixed_replicas"] = 1

    try:
        request(args.api, "/healthz")
        request(args.api, "/api/mode", mode_payload)
    except (urllib.error.URLError, OSError) as exc:
        print(f"CloudPilot API is unavailable at {args.api}: {exc}", file=sys.stderr)
        print("Start it first with ./scripts/dev-local.sh", file=sys.stderr)
        return 1

    print(f"Streaming {args.scenario} telemetry in {args.mode} mode. Press Ctrl+C to stop.")
    index = 0
    while running and (args.samples == 0 or index < args.samples):
        try:
            status = request(args.api, "/api/status")
            replicas = max(1, int(status["current_replicas"]))
            rps = max(0.0, workload(index, args.scenario) + randomizer.uniform(-2.0, 2.0))
            capacity = replicas * 20.0
            overload = max(0.0, rps - capacity) / max(1.0, capacity)
            sample = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_rate": round(rps, 3),
                "cpu_percent": round(min(99.0, 18 + rps / replicas * 2.7), 3),
                "memory_mb": round(82 + replicas * 34 + rps * 0.45, 3),
                "p95_latency_ms": round(90 + rps * 1.4 + overload * 650 + randomizer.uniform(0, 18), 3),
                "error_rate": round(min(0.35, overload * 0.12), 5),
                "restart_count": 0,
            }
            request(args.api, "/api/telemetry", sample)
            decision = request(args.api, "/api/control/tick", {})
            print(
                f"#{index + 1:03d} {sample['request_rate']:6.1f} rps | "
                f"p95 {sample['p95_latency_ms']:6.0f} ms | replicas "
                f"{decision['current_replicas']}->{decision['desired_replicas']} | "
                f"forecast {decision['predicted_rps']:6.1f}"
            )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError) as exc:
            print(f"Fixture request failed: {exc}", file=sys.stderr)
        index += 1
        if running and (args.samples == 0 or index < args.samples):
            time.sleep(max(0.2, args.interval))
    print("Fixture stream stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
