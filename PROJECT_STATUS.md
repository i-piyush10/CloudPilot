# Project Status Report: CloudPilot

## 1. Project Overview

* **What is this project?** CloudPilot is a local-first experimental platform and educational prototype for Kubernetes autoscaling operations.
* **What problem does it solve?** It provides a practical, zero-cost environment to compare different autoscaling strategies (fixed, reactive, and predictive) against the same workload, demonstrating how ML-based predictive scaling can improve resource efficiency and reduce latency spikes compared to standard reactive scaling.
* **What is the main objective?** To serve as an educational prototype and evaluation framework for predictive autoscaling, bounded anomaly detection, and controlled self-healing without requiring a heavy, expensive cloud setup.

## 2. Technology Stack

* **Programming languages**: Python (Backend & Workload), TypeScript/JavaScript (Frontend)
* **Frameworks**: FastAPI (Backend REST API), React and Vite (Frontend UI)
* **Libraries**: Recharts (Frontend charts), Prometheus Client (Python metrics)
* **Database**: SQLite (Local experiment and telemetry storage)
* **APIs**: Kubernetes API (for scaling and patching resources)
* **Tools and other technologies**: Docker, Docker Compose, Kubernetes (kind/Minikube), Prometheus, Grafana, OpenTelemetry Collector, Locust (Load generation)

## 3. Project Architecture

* **Explain the overall architecture**: The project consists of a sample FastAPI workload instrumented with OpenTelemetry and Prometheus, a Locust load generator, and a FastAPI control plane that manages scaling. A React UI visualizes the state.
* **Explain how the different components/modules communicate**:
  * Locust sends HTTP traffic to the Workload.
  * The Workload exposes Prometheus metrics and sends OTLP traces to the OpenTelemetry Collector.
  * Prometheus scrapes metrics from the Workload.
  * The Control Plane (Backend) periodically queries Prometheus for metrics, stores them in SQLite, runs a predictive model, and makes scaling decisions.
  * The Control Plane issues patch commands to the Kubernetes API to adjust replicas.
  * The React Frontend polls the Control Plane API to display live charts, logs, and experiment controls.
* **Explain the complete workflow from input to output**: User triggers load via Locust -> Workload CPU usage and requests increase -> Prometheus scrapes metrics -> Control Plane collects metrics -> Predictor calculates future request rate -> Decision engine bounds the replica count and applies it to the cluster -> UI displays the new state and metrics.

## 4. Folder and File Analysis

* `backend/app/`: The core control plane.
  * `controller.py`: The decision engine that manages scaling modes, bounds, cooldowns, and anomaly detection.
  * `predictor.py`: Implements a lightweight CPU-only linear trend predictor.
  * `store.py`: SQLite database abstraction for persisting telemetry, decisions, and experiments.
  * `cluster.py`: Adapters for both simulated and actual Kubernetes API interactions.
  * `collector.py`: Prometheus query client.
* `workload/app/`: The sample FastAPI application.
  * `main.py`: Simulates CPU work using SHA-256 hashing and exposes controllable fault injection endpoints.
* `frontend/src/`: The React control center.
  * `App.tsx`: The main dashboard containing live Recharts visualizations and control panels.
* `deploy/`: Contains Kubernetes manifests and Docker Compose configurations for the observability stack (Prometheus, Grafana, OpenTelemetry).
* `load-tests/`: Contains `locustfile.py` for defining load scenarios (spike, ramp, constant).
* `scripts/`: Helper bash scripts to bootstrap the cluster, deploy, run load, and execute experiments.

## 5. Currently Implemented Features

* **Predictive Scaling Mode**: Uses least-squares linear regression to forecast future requests per second (RPS) and scales proactively. Implemented in `predictor.py` and `controller.py`.
* **Standard HPA Scaling Mode**: Delegates scaling to standard Kubernetes Horizontal Pod Autoscaler based on CPU utilization.
* **Fixed Scaling Mode**: Maintains a stable baseline of replicas.
* **Safety Bounds & Cooldowns**: Prevents runaway scaling by enforcing max/min replicas, cooldown periods, and prediction confidence thresholds.
* **Experiment Runner**: Automates the recording of telemetry and calculation of p95 latency, error rates, and resource usage over a specific timeframe (implemented via `/api/experiments`).
* **Controlled Fault Injection**: Allows manual triggering of latency, CPU, and error faults in the workload to test anomaly detection.
* **Live Dashboard**: A fully working React UI with auto-refreshing area/line charts for request rate, latency, and errors.
* **Simulation Mode**: Can run without Kubernetes using in-memory mock scaling for rapid UI development.

## 6. Partially Implemented Features

* **Anomaly Detection**: The system currently defines conditions for `high_latency`, `high_error_rate`, `high_memory`, and `restart_loop`. While latency and error rate detections are fully working based on real telemetry, the `restart_loop` detection relies on a metric that is not properly collected yet (see Bugs section).

## 7. Missing Features

* **Advanced Forecasting Models**: The project strictly uses a short-horizon linear trend predictor. More complex models (e.g., ARIMA, LSTM, Exponential Smoothing) are not implemented, as it aims to be lightweight.
* **Automated Rollback/Advanced Healing**: Self-healing is strictly limited to an allow-listed "rollout restart". Complex automated remediations (like rolling back deployments) are missing.
* **High Availability**: The control plane uses a local SQLite database and is not designed to run in a highly available, multi-replica mode.

## 8. Current Bugs and Issues

* **Confirmed Bug in Telemetry Collection**: In `backend/app/collector.py` (Line 48), the `restart_count` is hardcoded to `0` (`restart_count=0`). As a result, the `restart_loop` anomaly condition defined in `controller.py` will never automatically trigger based on real cluster telemetry, because the backend is not querying Prometheus for pod restarts.
* **Configuration Issue**: The Grafana link in the UI depends on running the full stack, but there is no built-in readiness check in the UI to confirm Grafana is actually up before enabling the link (it relies purely on an environment variable flag).

## 9. Project Progress

* **Estimated Progress**: ~90-95% complete.
* **Assessment**: As an educational prototype and viva project, the implementation is highly complete. The core objective (comparing fixed, HPA, and predictive scaling) is fully achievable. The frontend, backend, workload, and deployment configurations are thoroughly integrated and functional. The only notable missing piece is fixing the restart count metric for full anomaly detection.

## 10. Remaining Work

* **High Priority**: 
  * Fix the `restart_count` telemetry query in `collector.py` to actually fetch pod restarts from Prometheus.
* **Medium Priority**: 
  * Implement alternative basic prediction models (e.g., moving average) to allow comparison between different predictive algorithms.
* **Low Priority / Improvements**: 
  * Migrate from SQLite to PostgreSQL if persistence across container restarts becomes a strict requirement.
  * Add UI indicators for Prometheus/Grafana connection health rather than assuming based on environment variables.

## 11. How to Complete the Remaining Work

* **Fixing Restart Count (High Priority)**:
  * **File to modify**: `backend/app/collector.py`
  * **Action**: Add a new query using the Prometheus client to fetch restarts. For example: `self.query('sum(kube_pod_container_status_restarts_total{namespace="cloudpilot", container="workload"})')`. Pass this queried value to the `TelemetryIn` constructor instead of `0`.

## 12. Current Project Workflow

1. **Initialization**: User starts the stack via Docker Compose or Kubernetes scripts.
2. **Setup**: User opens the React UI, selects a scaling mode (e.g., Predictive), and starts an experiment.
3. **Load Generation**: A Locust script is executed to simulate traffic (e.g., a sudden traffic spike).
4. **Processing & Telemetry**: The Workload processes the traffic; Prometheus scrapes the CPU usage, latency, and HTTP request metrics.
5. **Control Loop**: Every few seconds, the Control Plane fetches metrics from Prometheus, writes them to SQLite, and runs the `LinearTrendPredictor`.
6. **Decision Execution**: If the forecast confidence is high enough and cooldowns have passed, the Control Plane issues a patch to the Kubernetes API to adjust deployment replicas.
7. **Visualization**: The React UI polls the Control Plane every 5 seconds, updating the live charts and the audit log of scaling decisions.

## 13. Project Review / Viva Preparation

* **Basic**: What is the purpose of this project? 
  * *Answer*: To provide a local platform for comparing traditional reactive autoscaling (HPA) with predictive autoscaling based on machine learning.
* **Architecture**: How does the control plane scale the workload?
  * *Answer*: It reads metrics from Prometheus, calculates desired replicas based on the selected mode, and patches the Kubernetes Deployment directly via the Kubernetes REST API using a service account token.
* **Algorithm/Model**: How does your predictive model work?
  * *Answer*: It uses an ordinary least-squares linear regression over the last 60 telemetry samples to forecast the near-future request rate.
* **Safety**: What prevents the AI from scaling to 1000 pods if there is an error?
  * *Answer*: The decision engine clamps all outputs to a configured minimum and maximum replica count. It also ignores forecasts with low confidence scores and enforces a scale cooldown period.
* **Database**: Why use SQLite instead of a larger database?
  * *Answer*: SQLite is lightweight, requires no external dependencies, and is perfectly suited for an educational prototype running locally.
* **Future Scope**: How could you improve the predictor?
  * *Answer*: By replacing the linear regression model with a more advanced time-series forecasting model like ARIMA or an LSTM neural network to handle non-linear traffic patterns.

## 14. Final Status Summary

* **What is working?** The core scaling modes (Fixed, HPA, Predictive), Prometheus metric ingestion, SQLite persistence, React UI live charts, experiment running, and controlled fault injection.
* **What is incomplete?** The restart-loop anomaly detection relies on a hardcoded zero metric.
* **What is missing?** Advanced forecasting algorithms and automated complex self-healing (only rollout restarts are supported).
* **What should I work on next?** Fix the Prometheus query in `collector.py` so that pod restart counts are accurately recorded.
* **What should I prioritize before the next project review?** Ensure you can smoothly run the demo sequence (Fixed -> HPA -> Predictive) in the UI, and fix the `restart_count` bug so you can accurately demonstrate all anomaly detections.
