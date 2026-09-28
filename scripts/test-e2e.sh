#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

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

cleanup_report_permissions() {
  # Ensure the host user retains access to Playwright artifacts even if the container wrote them as root.
  compose run --rm --no-deps -T e2e sh -c "chown -R ${HOST_UID}:${HOST_GID} /tests/playwright-report" >/dev/null 2>&1 || true
}
trap cleanup_report_permissions EXIT

REPORT_DIR="$REPO_ROOT/e2e/playwright-report"
echo "Preparing Playwright report directory at ${REPORT_DIR}..."
mkdir -p "$REPORT_DIR"
if ! find "$REPORT_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +; then
  echo "Host cleanup failed, retrying via e2e container..."
  compose run --rm --no-deps -T e2e sh -c "rm -rf /tests/playwright-report/* && chown -R ${HOST_UID}:${HOST_GID} /tests/playwright-report"
fi

EXEC_OPTS=()
if [[ ! -t 1 ]]; then
  EXEC_OPTS+=(-T)
fi

UP_SERVICES=(db ollama backend frontend)

echo "Starting core services for E2E tests (${UP_SERVICES[*]})..."
compose up -d "${UP_SERVICES[@]}"

# Provide the frontend some time to finish building assets before running the suite.
sleep 5

echo "Running Playwright tests inside container..."
compose run --rm "${EXEC_OPTS[@]}" e2e npm run test:ci

echo "Playwright suite finished."
