#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/lint-backend.sh [--fix]

Runs Ruff against the Django codebase in a temporary backend container,
without starting PostgreSQL or Ollama. Pass --fix to apply automatic fixes
where possible.
USAGE
}

FIX_MODE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix)
      FIX_MODE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

IFS=' ' read -r -a DOCKER_COMPOSE_CMD <<< "${DOCKER_COMPOSE_CMD:-docker compose}"
if [[ ${#DOCKER_COMPOSE_CMD[@]} -eq 0 ]]; then
  echo "DOCKER_COMPOSE_CMD environment variable is empty" >&2
  exit 1
fi

RUN_OPTS=(--rm --no-deps)
if [[ ! -t 1 ]]; then
  RUN_OPTS+=(-T)
fi

compose() {
  "${DOCKER_COMPOSE_CMD[@]}" "$@"
}

RUFF_CMD=(ruff check .)
if [[ "$FIX_MODE" == true ]]; then
  RUFF_CMD+=(--fix)
fi

echo "Running ${RUFF_CMD[*]} in a temporary backend container..."
compose run "${RUN_OPTS[@]}" --entrypoint sh backend -c '
set -eu
cd /app
if ! command -v ruff >/dev/null 2>&1; then
  echo "Installing Ruff..."
  pip install --no-cache-dir --disable-pip-version-check -r requirements-dev.txt >/dev/null
fi
exec "$@"
' lint-backend "${RUFF_CMD[@]}"

echo "Backend linting complete."
