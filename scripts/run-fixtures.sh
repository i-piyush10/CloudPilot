#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_command="${CLOUDPILOT_PYTHON:-$project_dir/.venv/bin/python}"

if [[ ! -x "$python_command" ]]; then
  python_command="python3"
fi

exec "$python_command" "$project_dir/scripts/stream-fixtures.py" "$@"
