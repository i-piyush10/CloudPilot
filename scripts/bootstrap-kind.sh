#!/usr/bin/env bash
set -euo pipefail

cluster_name="${CLOUDPILOT_CLUSTER_NAME:-cloudpilot}"

for command_name in docker kind kubectl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing prerequisite: $command_name" >&2
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but its daemon is not running." >&2
  exit 1
fi

if ! kind get clusters | grep -Fxq "$cluster_name"; then
  kind create cluster --name "$cluster_name" --wait 120s
fi

kubectl config use-context "kind-$cluster_name" >/dev/null
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s

echo "kind cluster '$cluster_name' is ready with Metrics Server."
