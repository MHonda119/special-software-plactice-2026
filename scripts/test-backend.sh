#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/test-backend.sh [test-labels...]

Runs Django's test suite in a temporary backend container, without starting
PostgreSQL or Ollama, using SQLite (lecture_system.test_settings). When no
explicit test labels are supplied, the core app tests are executed by default.
USAGE
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
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

TEST_LABELS=("$@")
if [[ ${#TEST_LABELS[@]} -eq 0 ]]; then
  TEST_LABELS=(core)
fi

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

echo "Running Django tests in a temporary backend container..."
compose run "${RUN_OPTS[@]}" --entrypoint sh backend -c 'cd /app && DJANGO_SETTINGS_MODULE=lecture_system.test_settings python manage.py test "$@"' test-backend "${TEST_LABELS[@]}"

echo "Backend tests finished."
