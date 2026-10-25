#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash run_checks.sh [--dry-run] [docs|lint|test|all] [test-labels...]' \
    '' \
    'docs (default): check API documentation without Docker or Django.' \
    'lint: run the existing backend lint script (read-only, no --fix).' \
    'test: run the existing backend test script with optional Django labels.' \
    'all: check docs, lint, then run tests; stop on the first failure.' \
    '--dry-run: print commands without executing them.' \
    '' \
    'Docker Compose is required for lint/test/all, not for docs or dry-run.' \
    'DOCKER_COMPOSE_CMD is forwarded unchanged to the existing scripts.'
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
DRY_RUN=false

if [[ "${1:-}" == '--dry-run' ]]; then
  DRY_RUN=true
  shift
fi
MODE="${1:-docs}"
if [[ $# -gt 0 ]]; then
  shift
fi

run() {
  if [[ "$DRY_RUN" == true ]]; then
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

case "$MODE" in
  -h|--help)
    usage
    exit 0
    ;;
  docs|lint)
    if [[ $# -gt 0 ]]; then
      printf '%s does not accept test labels or options\n' "$MODE" >&2
      usage >&2
      exit 2
    fi
    ;;
  test|all)
    ;;
  *)
    printf 'Unknown mode: %s\n' "$MODE" >&2
    usage >&2
    exit 2
    ;;
esac

cd -- "$REPO_ROOT"
if [[ "$MODE" == docs || "$MODE" == all ]]; then
  run python3 "$SCRIPT_DIR/api_inventory.py" --check-docs
fi
if [[ "$MODE" == lint || "$MODE" == all ]]; then
  run bash "$REPO_ROOT/scripts/lint-backend.sh"
fi
if [[ "$MODE" == test || "$MODE" == all ]]; then
  run bash "$REPO_ROOT/scripts/test-backend.sh" "$@"
fi
