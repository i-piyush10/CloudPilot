# Demo and evaluation runbook

## Fast demonstration with Docker Compose

1. Start everything with `docker compose up --build`.
2. Open the CloudPilot UI at `http://localhost:8080` and Grafana at `http://localhost:3000`.
3. Select **Fixed**, set one replica, and start a spike experiment.
4. Run `./scripts/run-load.sh spike` in another terminal.
5. Show request rate, p95 latency, decisions, and the completed experiment summary.
6. Repeat in **Predictive** mode and explain the forecast, confidence threshold, replica bounds, and cooldown.
7. Use **Inject latency fault** or **Inject error fault** and show the incident record.

Simulation mode changes a safe in-memory replica model. Use it for UI development and early reviews; use kind for the final Kubernetes proof.

## Final Kubernetes demonstration

```bash
./scripts/bootstrap-kind.sh
./scripts/deploy-local.sh
./scripts/port-forward.sh
```

In a second terminal:

```bash
./scripts/run-experiment.sh fixed spike
./scripts/run-experiment.sh hpa spike
./scripts/run-experiment.sh predictive spike
```

For a shorter classroom rehearsal, set `CLOUDPILOT_LOAD_DURATION=90s` before `run-load.sh`. Use the normal duration for measured results.

Useful proof commands:

```bash
kubectl get pods,hpa -n cloudpilot -w
kubectl logs -n cloudpilot deployment/cloudpilot-control-plane
kubectl logs -n cloudpilot deployment/otel-collector
```

## Fair evaluation rules

- Use the same cluster resources, application image, request mix, scenario, duration, and initial replicas for every mode.
- Allow a cool-down between runs and record the exact configuration.
- Execute at least five repetitions per mode; report median and interquartile range as well as individual runs.
- Treat fixed allocation as the baseline and Kubernetes HPA as the standard reactive comparator.
- Never describe an expected improvement as an experimental result.

Record:

- Mean and maximum p95 latency
- Mean error rate and failed requests
- Replica-seconds as the resource-efficiency proxy
- Time from traffic change to a ready additional pod
- Forecast mean absolute error or root mean squared error
- Number of scaling actions and oscillations
- Anomaly detection time and recovery time

The API-generated experiment summary contains measured sample count, request rate, latency, error rate, and scaling-action count. Locust CSV files in `results/` provide request-level evidence for the report.

## Expected limitations to state in the viva

- The workload predictor is a lightweight short-horizon model, not a universal traffic forecaster.
- Local kind results demonstrate comparative behavior, not internet-scale capacity.
- SQLite and a single control-plane instance are appropriate for the prototype, not a highly available production service.
- Recovery policies are predefined because unconstrained AI-generated infrastructure commands would be unsafe.
