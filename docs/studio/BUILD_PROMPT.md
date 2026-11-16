You are building Studio v3 in this repo, from scratch, as far as you can get in one run. Work phase by phase without stopping to ask; decide and keep going. Ask only if something would destroy data.

## Read first, in this order
1. `AGENTS.md` (repo rules: smallest complete change, reuse before writing, verify before deleting).
2. `docs/studio/CHECKLIST.md` (the build order, phases 0 to 9, and the only progress tracker).
3. `docs/studio/PAGES.md` (the spec: 9 pages, inputs, outputs, acceptance ids H-, B-, K-, O-, V-, P-, L-, C-, Y-, X-).
4. `docs/studio/PLAN.md` §3 principles, §5 backend architecture, §5.1 engine, §5.2 API.
5. `docs/studio/REUSE.md` (what to import or lift from Screener, Research, ML and `chart_engine`).
6. `docs/studio/FEATURES_AND_OUTPUTS.md` §4 metric set and §10 customisation; `FRONTEND.md` §3-§9.
Read `REVIEW.md`, `COMPETITORS.md` and `OPEN_SOURCE.md` only when a decision needs the reason.
Do not read `docs/screener_v2_optimization/Screener V2 Master Audit Prompt.md`.

## Where things go
- Backend: `backend/app/services/studio_v3/` (`registry.py`, `core/*`, `features/*`), router under `/api/studio-v3/`, registered in `backend/main.py`. Jobs use the existing `backend/app/services/studio/jobs.py` `JobStore` (shared by every lab; do not move it).
- Frontend: Studio is the fourth lab: `frontend/src/modules/studio/studioLab.ts`, configured like `modules/screener/screenerLab.ts`, on the shared workspace (`FeatureView`, `Inspector`, `Hero`, `kit/*`, `RunCompare`, share). Route `frontend/src/app/studio/[[...slug]]/page.tsx`. Add Studio back to the nav in `frontend/src/components/GlobalLayout.jsx`.
- Tests: `backend/tests/test_studio_v3_*.py`; frontend e2e beside the existing lab specs in `frontend/e2e/`.
- Old Studio is already deleted. `components/chart_engine/` stays until phase 4 ports its maths (it still serves `/trade`).

## How to work each phase
1. Tick items in `docs/studio/CHECKLIST.md` as they land.
2. Each item is done only when its acceptance ids in `PAGES.md` pass as real tests (backend pytest, Playwright for UI and budgets).
3. Run the narrowest tests while working; at the end of a phase run all Studio tests plus the other labs' backend tests (`cd backend && uv run pytest`), `npm run typecheck` and `npm run lint` in `frontend/`.
4. Look at what you built: start the dev servers via the preview tools, open every new page, screenshot at 1440 and 1024 in dark and light, fix what looks wrong, then look again.
5. Commit and push to `main` after each verified chunk. Stage only your own files. Never use `--no-verify`; if the pre-commit hook (ruff, typecheck, lint, secrets) fails on your code, fix the code.
6. Then go straight to the next phase.

## Hard rules
- Real data only: the parquets in `data/` (`market_universe.parquet` daily, `market_universe_hourly.parquet` hourly for 23 names, `data/fundamentals/`). No mock numbers, no invented results, no fake fixtures shown in the UI. Test fixtures are fine in tests.
- The data refresh is phase 9: do not fetch or rewrite any parquet in phases 0-8. Show the data honestly in the limits popover (mixed adjustment, most tickers end 2026-01-28 to 2026-02-01, hourly for 23 names). The freshness pill shows the real age but, until phase 9, Live runs on stale data with the red pill shown instead of being blocked.
- Engines: numba vector engine + event engine sharing one fill model (next open default; worse-first when stop and target hit in one bar; bar magnifier only where hourly exists). They must match trade for trade.
- Licences: never ship vectorbt OSS (Commons Clause), backtesting.py or PineTS (AGPL), backtrader or freqtrade (GPL), nautilus (LGPL) code. You may read their whole source to understand how a feature works, then write our own implementation from that understanding: no copied code, no pasted snippets, no ported files line by line. They may also serve as test oracles (run them locally to compare numbers; never import them in shipped code). Any other dependency that gives better output or speed is fine; keep a fallback.
- One canonical `metrics.py` (phase 0 merges the existing copies; other labs must stay green).
- The verdict and certificate are computed on the server only; the browser never posts results to be certified.
- UI style (Outputs v2): one lead figure or one-line finding per card; no taglines, helper text or secondary labels; if a screen needs them, fix the layout. Every page has empty, loading, error and "skipped, because..." states; unknown values show "—" with the reason in a tooltip.
- Never touch or clean `research_exports/`.
- Do not delete anything outside Studio without checking the graph (`codebase-memory-mcp`), `rg`, route registration and a smoke test.
- At most one subagent at a time; do the main work yourself.

## Order
Phase 0 engine → 1 Backtest end to end + Home + agent API → 2 Build → 3 Optimise, Validate, alerts → 4 Chart → 5 Portfolio and Live → 6 Library → 7 cross-page finish → 8 phone. Stop before phase 9.
If a budget in `PAGES.md` §10.7 cannot be met, record the measured number in the checklist and move on.

## When you stop
Leave the checklist accurate. Reply with: phases finished, last commit hash, tests run with results, what is unfinished and why, and any spec item you changed and why.
