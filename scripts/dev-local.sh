#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_command="${CLOUDPILOT_PYTHON:-$project_dir/.venv/bin/python}"
api_port="${CLOUDPILOT_DEV_API_PORT:-18000}"
workload_port="${CLOUDPILOT_DEV_WORKLOAD_PORT:-18001}"

if [[ ! -x "$python_command" ]]; then
  echo "Python environment missing. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements-dev.txt -r workload/requirements-dev.txt" >&2
  exit 1
fi
command -v npm >/dev/null 2>&1 || { echo "npm is required. Install Node.js, then run npm install in frontend/." >&2; exit 1; }

cleanup() {
  for job in $(jobs -pr); do
    kill "$job" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

env PYTHONPATH="$project_dir/workload" "$python_command" -m uvicorn app.main:app \
  --host 127.0.0.1 --port "$workload_port" &
env PYTHONPATH="$project_dir/backend" CLOUDPILOT_MODE=simulation \
  CLOUDPILOT_DATABASE="$project_dir/cloudpilot.db" \
  CLOUDPILOT_WORKLOAD_URL="http://127.0.0.1:$workload_port" \
  CLOUDPILOT_PROMETHEUS_URL="http://127.0.0.1:19090" \
  CLOUDPILOT_SCALE_COOLDOWN_SECONDS="${CLOUDPILOT_SCALE_COOLDOWN_SECONDS:-8}" \
  CLOUDPILOT_CONTROL_INTERVAL_SECONDS="${CLOUDPILOT_CONTROL_INTERVAL_SECONDS:-60}" \
  "$python_command" -m uvicorn app.main:app --host 127.0.0.1 --port "$api_port" &

cd "$project_dir/frontend"
env VITE_API_PROXY="http://127.0.0.1:$api_port" npm run dev -- --host 127.0.0.1
