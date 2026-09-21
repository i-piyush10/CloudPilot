#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  for job in $(jobs -pr); do
    kill "$job" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

kubectl -n cloudpilot port-forward service/frontend 8080:80 &
kubectl -n cloudpilot port-forward service/control-plane 8000:8000 &
kubectl -n cloudpilot port-forward service/workload 8001:8001 &
kubectl -n cloudpilot port-forward service/prometheus 9090:9090 &
kubectl -n cloudpilot port-forward service/grafana 3000:3000 &

echo "CloudPilot UI: http://localhost:8080"
echo "API docs:      http://localhost:8000/docs"
echo "Workload:      http://localhost:8001/api/work"
echo "Prometheus:    http://localhost:9090"
echo "Grafana:       http://localhost:3000/d/cloudpilot-main"
echo "Press Ctrl+C to stop port forwarding."
wait
