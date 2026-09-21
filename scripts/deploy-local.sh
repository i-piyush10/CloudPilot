#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cluster_name="${CLOUDPILOT_CLUSTER_NAME:-cloudpilot}"

for command_name in docker kind kubectl; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "Missing prerequisite: $command_name" >&2; exit 1; }
done

docker build -t cloudpilot/workload:local "$project_dir/workload"
docker build -t cloudpilot/control-plane:local "$project_dir/backend"
docker build -t cloudpilot/frontend:local "$project_dir/frontend"

kind load docker-image --name "$cluster_name" \
  cloudpilot/workload:local cloudpilot/control-plane:local cloudpilot/frontend:local
kubectl config use-context "kind-$cluster_name" >/dev/null
kubectl apply -k "$project_dir/deploy/kubernetes"
kubectl rollout status deployment/cloudpilot-workload -n cloudpilot --timeout=180s
kubectl rollout status deployment/cloudpilot-control-plane -n cloudpilot --timeout=180s
kubectl rollout status deployment/cloudpilot-frontend -n cloudpilot --timeout=180s
kubectl rollout status deployment/prometheus -n cloudpilot --timeout=180s
kubectl rollout status deployment/otel-collector -n cloudpilot --timeout=180s
kubectl rollout status deployment/grafana -n cloudpilot --timeout=180s

kubectl get pods -n cloudpilot
echo "Deployment complete. Run ./scripts/port-forward.sh next."
