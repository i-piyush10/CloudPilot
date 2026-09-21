#!/usr/bin/env bash
set -euo pipefail

api="${CLOUDPILOT_API_URL:-http://localhost:8000}"
workload="${CLOUDPILOT_WORKLOAD_URL:-http://localhost:8001}"

curl --fail --silent "$api/healthz" >/dev/null
curl --fail --silent "$workload/healthz" >/dev/null
curl --fail --silent "$workload/api/work?iterations=1000" >/dev/null
curl --fail --silent "$api/api/status" >/dev/null
curl --fail --silent -X POST "$api/api/control/tick" >/dev/null

echo "CloudPilot smoke test passed for API and workload."
