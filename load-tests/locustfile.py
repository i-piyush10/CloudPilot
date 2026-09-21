from __future__ import annotations

import os
import random

from locust import HttpUser, LoadTestShape, between, task


SCENARIO = os.getenv("CLOUDPILOT_SCENARIO", "constant")


class CloudPilotUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(12)
    def normal_work(self):
        iterations = 8_000 if SCENARIO != "spike" else 25_000
        self.client.get(f"/api/work?iterations={iterations}", name="/api/work")

    @task(1)
    def realistic_slow_request(self):
        delay = random.randint(20, 100) if SCENARIO != "failure" else 1_000
        self.client.get(f"/api/work?iterations=1000&delay_ms={delay}", name="/api/work delayed")

    @task(1)
    def controlled_error(self):
        if SCENARIO == "failure":
            self.client.get("/api/work?iterations=100&fail=true", name="/api/work controlled error")


class CloudPilotShape(LoadTestShape):
    """Deterministic profiles so every scaling mode receives the same demand shape."""

    def tick(self):
        elapsed = self.get_run_time()
        if SCENARIO == "ramp":
            return (min(80, 10 + int(elapsed // 30) * 10), 4)
        if SCENARIO == "spike":
            return (15, 5) if elapsed < 60 else ((100, 30) if elapsed < 120 else (20, 15))
        if SCENARIO == "periodic":
            return ((70, 15) if int(elapsed // 45) % 2 else (15, 8))
        if SCENARIO == "failure":
            return (30, 6)
        return (20, 5)
