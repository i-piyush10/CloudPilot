#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:-predictive}"
scenario="${2:-spike}"
api="${CLOUDPILOT_API_URL:-http://localhost:8000}"
python_command="${CLOUDPILOT_PYTHON:-$project_dir/.venv/bin/python}"

case "$mode" in fixed|hpa|predictive) ;; *) echo "Mode must be fixed, hpa, or predictive" >&2; exit 2 ;; esac
case "$scenario" in constant|ramp|spike|periodic|failure) ;; *) echo "Unsupported scenario" >&2; exit 2 ;; esac

payload="{\"name\":\"$scenario-$mode\",\"scenario\":\"$scenario\",\"mode\":\"$mode\",\"duration_seconds\":300}"
experiment_id="$(curl --fail --silent -X POST -H 'Content-Type: application/json' -d "$payload" "$api/api/experiments" | "$python_command" -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
curl --fail --silent -X POST "$api/api/experiments/$experiment_id/start" >/dev/null

echo "Experiment $experiment_id started: $mode / $scenario"
env CLOUDPILOT_PYTHON="$python_command" CLOUDPILOT_RESULT_PREFIX="$scenario-$mode" "$project_dir/scripts/run-load.sh" "$scenario"
curl --fail --silent -X POST "$api/api/experiments/$experiment_id/complete"
echo
