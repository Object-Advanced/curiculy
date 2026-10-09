#!/usr/bin/env bash
# Run the Playwright suite against a throwaway Curiculy app.
#
#   e2e/run.sh                         whole suite
#   e2e/run.sh --project=functional    one project
#   e2e/run.sh --update-snapshots      accept intended visual changes
#
# Every run starts a fresh app with empty databases, because the suite
# registers a household with a single-use invite key. Everything runs in the
# separate curiculy-e2e Compose project; the real `api` container is never
# touched.
set -euo pipefail

cd "$(dirname "$0")"
export E2E_UID="${E2E_UID:-$(id -u)}"
export E2E_GID="${E2E_GID:-$(id -g)}"

compose() { docker compose -f compose.yml "$@"; }
cleanup() { compose down --volumes --remove-orphans > /dev/null 2>&1 || true; }

trap cleanup EXIT
cleanup
compose up --detach --wait curiculy-app
compose run --rm -T playwright sh -c 'npm ci --no-audit --no-fund && npx playwright test "$@"' playwright "$@"
