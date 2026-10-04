# E2E visual smoke tests

`playwright` is already a dependency (see `playwright.config.ts`). Run: `npx playwright test e2e/research.spec.ts`.
First run: add `--update-snapshots` to create baselines. Needs the backend for data-bearing pages; set
`PLAYWRIGHT_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=...` to target a running server.
