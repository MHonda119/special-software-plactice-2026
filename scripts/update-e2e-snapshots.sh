#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage: scripts/update-e2e-snapshots.sh [--] [PLAYWRIGHT_ARGS...]

Regenerate Playwright screenshot baselines inside the containerized E2E runner.
Arguments after "--" are forwarded directly to `npx playwright test`.
Examples:
  scripts/update-e2e-snapshots.sh
  scripts/update-e2e-snapshots.sh -- --grep "Start page"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift

done

PLAYWRIGHT_ARGS=("$@")

: "${HOST_UID:=$(id -u)}"
: "${HOST_GID:=$(id -g)}"
export HOST_UID HOST_GID

DEFAULT_COMPOSE_CMD="docker compose --profile e2e"
IFS=' ' read -r -a DOCKER_COMPOSE_CMD <<< "${DOCKER_COMPOSE_CMD:-$DEFAULT_COMPOSE_CMD}"
if [[ ${#DOCKER_COMPOSE_CMD[@]} -eq 0 ]]; then
  echo "DOCKER_COMPOSE_CMD environment variable is empty" >&2
  exit 1
fi

compose() {
  "${DOCKER_COMPOSE_CMD[@]}" "$@"
}

TESTS_DIR="$REPO_ROOT/e2e/tests"
if [[ ! -d "$TESTS_DIR" ]]; then
  echo "Playwright tests directory not found at $TESTS_DIR" >&2
  exit 1
fi

TESTS_MOUNT="${TESTS_DIR}:/tests/tests"

cleanup_tests_permissions() {
  local exec_opts=()
  if [[ ! -t 1 ]]; then
    exec_opts+=(-T)
  fi

  compose run --rm --no-deps "${exec_opts[@]}" -v "$TESTS_MOUNT" e2e \
    sh -c "chown -R ${HOST_UID}:${HOST_GID} /tests/tests" >/dev/null 2>&1 || true
}
trap cleanup_tests_permissions EXIT

REPORT_DIR="$REPO_ROOT/e2e/playwright-report"
mkdir -p "$REPORT_DIR"

EXEC_OPTS=()
if [[ ! -t 1 ]]; then
  EXEC_OPTS+=(-T)
fi

UP_SERVICES=(db ollama backend frontend)

echo "Starting core services for E2E snapshot updates (${UP_SERVICES[*]})..."
compose up -d "${UP_SERVICES[@]}"

sleep 5

RUN_ARGS=(
  run --rm
  "${EXEC_OPTS[@]}"
  -v "$TESTS_MOUNT"
)

echo "Updating Playwright screenshot baselines..."
compose "${RUN_ARGS[@]}" e2e npm run test -- --update-snapshots "${PLAYWRIGHT_ARGS[@]}"

echo "Screenshot baselines refreshed under e2e/tests."
