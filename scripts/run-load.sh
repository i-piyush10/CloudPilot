#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scenario="${1:-spike}"
host="${CLOUDPILOT_LOAD_HOST:-http://localhost:8001}"

case "$scenario" in
  constant) users=20; spawn_rate=5; duration=5m ;;
  ramp) users=60; spawn_rate=2; duration=5m ;;
  spike) users=100; spawn_rate=25; duration=3m ;;
  periodic) users=45; spawn_rate=8; duration=5m ;;
  failure) users=30; spawn_rate=6; duration=3m ;;
  *) echo "Scenario must be constant, ramp, spike, periodic, or failure" >&2; exit 2 ;;
esac

python_command="${CLOUDPILOT_PYTHON:-python3}"
duration="${CLOUDPILOT_LOAD_DURATION:-$duration}"
result_prefix="${CLOUDPILOT_RESULT_PREFIX:-$scenario}"
mkdir -p "$project_dir/results"
env CLOUDPILOT_SCENARIO="$scenario" PYTHONPATH="$project_dir/load-tests" "$python_command" -m locust \
  -f "$project_dir/load-tests/locustfile.py" --headless --host "$host" \
  --users "$users" --spawn-rate "$spawn_rate" --run-time "$duration" \
  --csv "$project_dir/results/${result_prefix}"
