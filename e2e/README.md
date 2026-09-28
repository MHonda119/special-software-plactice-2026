# Playwright E2E tests

This directory hosts the containerized Playwright suite that verifies the
end-to-end flow of the Simple Chat UI against the docker-compose stack.

## Local execution

1. Ensure the application services are running (database, backend, frontend, and
   their dependencies) via docker compose.
2. Execute `scripts/test-e2e.sh` from the repository root. The script will start
   the services when necessary and run the tests inside the dedicated Playwright
   container.

### Getting the run summary

After `scripts/test-e2e.sh` finishes, Playwright prints a short pass/fail
summary (tests executed, failures, skipped, duration) to the script's stdout.
This is usually enough when you only need a quick status check (for example in
CI logs). If you need to re-print the same textual summary later, you can run
the Playwright CLI inside the e2e container:

```bash
docker compose --profile e2e run --rm e2e npx playwright test --reporter line
```

For a richer breakdown (per-test status, traces, screenshots), open the HTML
report that `scripts/test-e2e.sh` writes to `e2e/playwright-report/`. The
directory is recreated on every run so it always reflects the latest suite:

```bash
cd e2e
npx playwright show-report
```

This command launches a local web server that renders the stored report, so you
can review failures and download the attached artifacts any time after the test
run.

### Capturing page transition videos

Playwright now records a video for every test run (not only failures). The
videos are saved under the HTML report directory that `scripts/test-e2e.sh`
prepares (`e2e/playwright-report/` by default) using the standard Playwright
layout:

```bash
docker compose --profile e2e run --rm e2e npx playwright show-report
```

Open the report and navigate to a test entry to download the corresponding
`video.webm`. This captures the entire page transition flow exercised in the
specs, making it easy to share regressions or walkthroughs.

### Managing screenshot baselines

The `start-page.spec.ts` test asserts the rendered menu screen using
`expect(page).toHaveScreenshot(...)`. Because the containerized runner does not
mount the test sources read/write, generate baselines from the host machine (the
frontend still runs inside Docker):

```bash
# From the repo root, ensure the stack is up via docker compose up -d ...
cd e2e
PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test tests/start-page.spec.ts --update-snapshots
```

Playwright stores the expected PNG inside
`e2e/tests/start-page.spec.ts-snapshots/` (one file per browser, e.g.
`menu-page-chrome-linux.png`). Commit baseline updates to keep CI deterministic.
Regular runs (via `scripts/test-e2e.sh`) will compare the freshly captured
screenshot against those committed files and fail with a diff if they diverge.

### Showing the HTML report via the container

If you prefer to reuse the containerized Playwright environment, run:

```bash
scripts/show-e2e-report.sh
```

The script mirrors the `test-e2e.sh` Docker Compose configuration, publishes
port 9323 by default, and executes `npx playwright show-report` inside the e2e
container. Once it prints `http://localhost:9323`, open that URL in your
browser. Use `--port` to change the exposed port or `--report-dir` if you stored
the report under a non-default directory name (relative to `e2e/`). The script
will exit early with guidance if no HTML report is present, so make sure
`scripts/test-e2e.sh` has been executed at least once beforehand.

## Adding tests

Add new `.spec.ts` files under `tests/`. The Playwright config already sets the
base URL to `http://frontend:3000`, so you can navigate using relative paths:
`await page.goto('/menu');`.
