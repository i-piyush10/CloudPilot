# CloudPilot

CloudPilot is a zero-cost, local-first experimental platform for comparing fixed Kubernetes replicas, standard Horizontal Pod Autoscaling (HPA), and lightweight ML-based predictive autoscaling. It also demonstrates bounded anomaly detection and controlled self-healing.

## What is included

- A containerized FastAPI sample workload with Prometheus metrics
- A FastAPI control plane with SQLite experiment storage
- A CPU-only linear-trend workload predictor with confidence scoring
- Fixed, HPA, and predictive scaling modes
- Bounded replica decisions, cooldowns, and an auditable decision log
- Controlled fault injection and self-healing demonstrations
- A React/Vite control center with live charts and experiment controls
- Prometheus and Grafana provisioning
- OpenTelemetry tracing with a local collector
- Docker Compose and local Kubernetes manifests
- Locust load scenarios and backend/frontend tests

## Quick start without Kubernetes

Prerequisites: Docker with Compose.

```bash
cp .env.example .env
docker compose up --build
Open:

CloudPilot UI: http://localhost:8080

Control-plane API docs: http://localhost:8000/docs

Sample workload: http://localhost:8001

Prometheus: http://localhost:9090

Grafana: http://localhost:3000

OpenTelemetry traces can be inspected with:

docker compose logs -f otel-collector
The Compose profile runs in simulation mode, so scaling decisions can be demonstrated without a Kubernetes cluster.

Local Kubernetes demo
Prerequisites: Docker, kubectl, and either kind or Minikube.

./scripts/bootstrap-kind.sh
./scripts/deploy-local.sh
./scripts/port-forward.sh
Then open:

http://localhost:8080

Run the load generator in another terminal:

./scripts/run-load.sh spike
For a recorded experiment:

./scripts/run-experiment.sh predictive spike
Repeat the experiment with fixed, hpa, and predictive modes to compare their behavior.

Only one autoscaling controller should own the workload at a time. Selecting predictive or fixed mode removes the HPA, while selecting HPA pauses CloudPilot replica writes.

Development
Backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
Start the backend:

python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
Frontend
cd frontend
npm install
npm run dev
Open:

http://127.0.0.1:5173/

Vite proxies /api requests to the local control plane.

The lightweight development setup does not start Prometheus, Grafana, or the OpenTelemetry Collector. Use Docker Compose or the Kubernetes deployment when the full observability stack is required.

Scaling modes
Fixed
Maintains a configured replica count and provides a baseline for comparison.

HPA
Uses Kubernetes Horizontal Pod Autoscaling based on CPU utilization.

Predictive
Uses a lightweight CPU-only linear-trend predictor to estimate near-future request demand and calculate the required replica count.

The predictive controller applies safety boundaries including:

Minimum and maximum replica limits

Forecast confidence thresholds

Scaling cooldowns

Capacity-per-pod limits

Bounded forecast extrapolation

Monitoring and observability
CloudPilot integrates:

Prometheus for metrics collection

Grafana for visualization

OpenTelemetry Collector for traces

Application-level request, latency, CPU, memory, and error metrics

Control-plane decision and incident logs

The system exposes health and metrics endpoints for the workload and control plane.

Fault injection and self-healing
CloudPilot includes controlled fault scenarios for demonstration:

Latency injection

Error injection

CPU stress

Anomaly detection

Allow-listed Kubernetes rollout restart

High-severity anomalies such as sustained error conditions can trigger a controlled recovery action.

Safety boundaries
Replica counts are clamped to configured minimum and maximum values.

Scaling requires sufficient telemetry and respects cooldown periods.

Self-healing actions are selected from an allow-list.

The UI cannot submit arbitrary shell commands.

Kubernetes commands use configured resource names and namespaces only.

This is an educational prototype, not a production autonomous-operations system.

Project layout
backend/        Control plane, predictor, store, cluster adapter
workload/       Instrumented sample application
frontend/       React control center
deploy/         Docker, Prometheus, Grafana, Kubernetes manifests
load-tests/     Locust workload scenarios
scripts/        Local setup, deployment, port-forwarding, demo helpers
docs/           Architecture and demonstration documentation
Evaluation
Run the same workload scenario in fixed, HPA, and predictive modes.

Compare:

p95 latency

Error rate

Replica-seconds

Scaling delay

Decision count

Forecast error

Anomaly detection time

Recovery time

Measured results should only be reported after the corresponding experiments have been executed.

Laptop sizing
The Compose simulation is the lightest option.

For the Kubernetes demonstration, approximately 4 CPU cores and 6 GB RAM should be allocated to Docker Desktop when possible. On an 8 GB laptop, close unrelated applications if the cluster becomes memory-constrained.

Documentation
See:

docs/ARCHITECTURE.md — system architecture and component boundaries

docs/DEMO.md — demonstration and evaluation runbook

PROJECT_STATUS.md — current implementation status

License
This project was developed as an academic capstone and experimental platform.
