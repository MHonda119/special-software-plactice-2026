#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/lint-frontend.sh [--fix]

Runs TypeScript type-checking and ESLint in a temporary frontend container,
without starting the backend or publishing host ports. Pass --fix to let
ESLint attempt auto-fixes (Prettier is intentionally not invoked to avoid
conflicting formatters).
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

ESLINT_CMD=(npm run lint)
if [[ "$FIX_MODE" == true ]]; then
  ESLINT_CMD+=(-- --fix)
fi

echo "Running frontend checks in a temporary container..."
# Keep checks isolated from the dev server's shared dependency volume.
compose run "${RUN_OPTS[@]}" --volume /usr/src/app/node_modules --entrypoint sh frontend -c '
set -eu
cd /usr/src/app
echo "Installing Node dependencies from package-lock.json..."
npm ci --no-audit --loglevel error
echo "Running TypeScript type-checks..."
npm run typecheck
echo "Running ESLint..."
exec "$@"
' lint-frontend "${ESLINT_CMD[@]}"

echo "Frontend linting complete."
