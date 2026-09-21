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
```

Open:

- CloudPilot UI: <http://localhost:8080>
- Control-plane API docs: <http://localhost:8000/docs>
- Sample workload: <http://localhost:8001>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (anonymous local access)

OpenTelemetry traces are exported locally and can be inspected with:

```bash
docker compose logs -f otel-collector
```

The Compose profile runs in `simulation` mode, so scaling decisions are visible without a Kubernetes cluster.

## Local Kubernetes demo

Prerequisites: Docker, `kubectl`, and either kind or Minikube. The scripts default to kind.

```bash
./scripts/bootstrap-kind.sh
./scripts/deploy-local.sh
./scripts/port-forward.sh
```

Then open <http://localhost:8080>. Run the load generator in another terminal:

```bash
./scripts/run-load.sh spike
```

For a recorded experiment, use the UI experiment notebook or run:

```bash
./scripts/run-experiment.sh predictive spike
```

Repeat that command with `fixed`, `hpa`, and `predictive`; CSV evidence is written to `results/` with separate filenames.

To switch among modes, use the UI or API. Only one autoscaling controller should own the workload at a time; selecting predictive or fixed mode removes the HPA, while selecting HPA pauses CloudPilot replica writes.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
make install
make test
./scripts/dev-local.sh
```

Open <http://127.0.0.1:5173/>. Do not open `frontend/index.html` using a `file://` URL: Vite must serve the React modules, and it proxies `/api` requests to the local control plane. Press `Ctrl+C` in the terminal to stop all three development services.

The lightweight development command does not start Prometheus, Grafana, or the OpenTelemetry Collector. The dashboard therefore labels Grafana as **full stack only**. Use `docker compose up --build` or the Kubernetes deployment to enable the Grafana link at <http://localhost:3000/d/cloudpilot-main>.

To populate the development dashboard with a deterministic real-time fixture stream, open another terminal and run:

```bash
cd /Users/omyad/Documents/Om/CloudPilot
./scripts/run-fixtures.sh --scenario spike --mode predictive
```

The streamer posts a new sample every two seconds and triggers a control decision. Use `Ctrl+C` to stop it. Other scenarios are `ramp`, `periodic`, and `constant`.

Python services run from `backend/` and `workload/`; the UI runs from `frontend/`.

## Safety boundaries

- Replica counts are clamped to configured minimum and maximum values.
- Scaling uses a cooldown and requires sufficient telemetry.
- Self-healing actions are selected from an allow-list.
- The UI cannot submit arbitrary shell commands.
- Kubernetes commands use configured resource names and namespaces only.
- This is an educational prototype, not a production autonomous-operations system.

## Project layout

```text
backend/        Control plane, predictor, store, cluster adapter
workload/       Instrumented sample application
frontend/       React control center
deploy/         Docker, Prometheus, Grafana, Kubernetes manifests
load-tests/     Locust workload scenarios
scripts/        Local setup, deployment, port-forwarding, demo helpers
tests/          End-to-end smoke tests
```

See [Architecture](docs/ARCHITECTURE.md) and [Demo and evaluation runbook](docs/DEMO.md) for the component boundaries and a faculty-ready demonstration sequence.

## Evaluation

Run the same load scenario in fixed, HPA, and predictive modes. Compare p95 latency, error rate, replica-seconds, scaling delay, decision count, forecast error, anomaly detection time, and recovery time. Do not report expected improvements as measured results until experiments are executed.

## Laptop sizing

The Compose simulation is the lightest option. For the Kubernetes demonstration, allocate approximately 4 CPU cores and 6 GB RAM to Docker; close unrelated applications on an 8 GB laptop. Grafana and OpenTelemetry can be temporarily scaled to zero if memory is constrained, without disabling the core controller.
