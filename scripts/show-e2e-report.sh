#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage: scripts/show-e2e-report.sh [--report-dir DIR] [--port PORT]

Run `npx playwright show-report` inside the containerized E2E test runner.
Options:
  --report-dir DIR  Relative path to the report directory (under e2e/). Defaults to 'playwright-report'.
  --port PORT       Host/guest port for the temporary report server. Defaults to 9323.
  -h, --help        Show this help message and exit.
EOF
}

DEFAULT_COMPOSE_CMD="docker compose --profile e2e"
IFS=' ' read -r -a DOCKER_COMPOSE_CMD <<< "${DOCKER_COMPOSE_CMD:-$DEFAULT_COMPOSE_CMD}"
if [[ ${#DOCKER_COMPOSE_CMD[@]} -eq 0 ]]; then
  echo "DOCKER_COMPOSE_CMD environment variable is empty" >&2
  exit 1
fi

compose() {
  "${DOCKER_COMPOSE_CMD[@]}" "$@"
}

REPORT_DIR="playwright-report"
PORT="${PLAYWRIGHT_REPORT_PORT:-9323}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report-dir)
      shift || { echo "Missing value for --report-dir" >&2; exit 1; }
      REPORT_DIR="$1"
      ;;
    --port)
      shift || { echo "Missing value for --port" >&2; exit 1; }
      PORT="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ -z "$PORT" || ! $PORT =~ ^[0-9]+$ ]]; then
  echo "--port must be a positive integer" >&2
  exit 1
fi

if [[ "$REPORT_DIR" = /* ]]; then
  echo "--report-dir must be a path relative to the e2e folder" >&2
  exit 1
fi

HOST_REPORT_DIR="$REPO_ROOT/e2e/$REPORT_DIR"
if [[ ! -d "$HOST_REPORT_DIR" ]]; then
  cat <<EOF >&2
Report directory '$HOST_REPORT_DIR' was not found.
Please run scripts/test-e2e.sh first so Playwright can generate an HTML report.
EOF
  exit 1
fi

if [[ -z "$(find "$HOST_REPORT_DIR" -mindepth 1 -print -quit)" ]]; then
  cat <<EOF >&2
Report directory '$HOST_REPORT_DIR' is empty.
Re-run scripts/test-e2e.sh to regenerate the Playwright report before launching the viewer.
EOF
  exit 1
fi

EXEC_OPTS=()
if [[ ! -t 1 ]]; then
  EXEC_OPTS+=(-T)
fi

REPORT_PATH_ESCAPED=$(printf '%q' "$REPORT_DIR")
PORT_ESCAPED=$(printf '%q' "$PORT")

COMMAND="cd /tests && npx playwright show-report ${REPORT_PATH_ESCAPED} --host 0.0.0.0 --port ${PORT_ESCAPED}"

echo "Launching Playwright report viewer on http://localhost:${PORT} (Ctrl+C to stop)..."
compose run --rm "${EXEC_OPTS[@]}" -p "${PORT}:${PORT}" -v "${HOST_REPORT_DIR}:/tests/${REPORT_DIR}" e2e bash -lc "$COMMAND"
