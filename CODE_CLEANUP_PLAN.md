# Code cleanup plan (awaiting approval)

How this was checked:
- **Backend imports:** mapped every module that `backend/main.py` imports, directly or indirectly (466 modules).
- **Routes vs frontend:** matched every mounted route against the URLs the frontend actually calls.
- **Frontend imports:** mapped every frontend file that any page imports (774 files).
- **v2 kept by design:** the v2 packages load their features dynamically (`importlib`), so they look unused to a static scan. They are all kept.

## 0. First, answers and one problem found

**Why two `src/` folders?** `frontend/src/` is the real app: `final start.sh` runs `npm run dev` inside `frontend/`. The root `src/` is the original project template, a shadcn starter with one page. The root `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs` and `bun.lock` belong to that template. Nothing runs from them.

**The backend does not start right now.** `app/api/macro.py` imports `app.services.macro.series_catalog`, and that package no longer exists (it shows as deleted in git). `main.py` crashes on import. This has to be fixed first, either by restoring the file from git or by unmounting `macro`. Otherwise nothing can be tested after cleanup.

## 1. SAFE: nothing imports or calls these (zero behavior change)

### Repo root
| Delete | Why |
|---|---|
| `src/` (root) | Unused template app |
| `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `bun.lock` (root) | Config for that template; `frontend/` has its own |
| `QUANT360_ENGINE_CORE/` | Standalone data-fetch scripts; no code imports or calls them. **Note:** `BulletproofDeltaSync_v5.py` looks like the script that refreshes the market data. Keep a copy if you still refresh data with it. |

Keep root `package.json` and `package-lock.json`: `docker/Dockerfile.nse-api` uses them (`stock-nse-india`).

### Backend: modules no running code imports
| Delete | Why |
|---|---|
| `app/api/liquidity.py` + `app/services/liquidity.py` | Old liquidity API, never mounted; replaced by `liquidity_api.py` + `liquidity_engine.py` |
| `app/api/monitor.py`, `app/api/monitor_v2.py` | Commented out in `main.py` ("Monitor page removed"). Also deletes the 190-line commented `/api/monitor` block inside `main.py` |
| `app/routers/ml_v2.py` | Never mounted; duplicates the `/api/ml/v2` routes `ml_api.py` already serves |
| `app/models/backtest.py`, `factors.py`, `indicators.py`, `pca.py`, `portfolio.py`, `regimes.py`, `scenarios.py`, `volatility.py` | Imported by nothing. `models/portfolio_models.py` and `models/research_schemas.py` stay (they are used) |
| `app/services/portfolio_audit.py`, `portfolio_brain.py`, `portfolio_hedging.py`, `portfolio_regimes.py`, `portfolio_risk.py`, `portfolio_strategy.py`, `portfolio_trading.py` | An old portfolio engine; they import only each other and nothing reaches them |
| `app/services/indicator_service.py`, `strategy_research_fix.py`, `yf_safety.py` | Imported by nothing |
| `app/strategies/` (`boll_breakout.py`, `mean_reversion.py`) | Imported by nothing |
| `app/services/design.md`, `app/services/regime_database.db`, `app/checkpoints/checkpoint-contract-run.pkl`, `app/api/demo_signals.json` | Stray notes, caches and test artifacts inside code folders; I'll grep each for use before deleting |
| `backend/backend/` (a nested `data/`), `backend/data_cache/`, `backend/expansion_review.json`, `backend/generate_data.py`, `backend/backend.log` | Leftovers; the log is recreated on start |
| `app/studio_v2/storage/strategies/contract-handoff_*.py` (45 files) + `http-paper-route_*.py` | Strategies saved by test runs. **Optional:** the Studio v2 database lists them, so this is a reset of Studio's saved strategies |

### Frontend: files no page imports (214 files)
| Delete | Files |
|---|---|
| `components/monitor/` | 19; monitor page removed |
| `components/macro/` (unused parts), `components/markets_daily/` (unused parts), `components/trading/`, `components/chart_engine/`, `components/portfolio/` (unused parts), `components/labs/` (unused parts), `components/landing/` | 18 + 15 + 16 + 34 + 13 + 10 + 9 |
| `components/ui/` (unused shadcn parts) | 22 |
| Singles: `GamificationRibbon.jsx`, `CommandBar.jsx`, `WatchlistSelector.jsx`, `Providers.js`, `hooks/usePerformance.js`, `useDataRefresh.js`, `useKeyboardShortcuts.js`, `usePrefetch.js`, `hooks/index.js`, `lib/apiClient.js`, `lib/cache.js`, `context/StrategyContext.js`, plus `components/terminal`, `hero`, `watchlist`, `auth` (unused parts) | about 20 |
| `frontend/output/` | Empty |

I would **not** delete the 20 unused `components/studio-v2/` files, the 9 `types/studio` files, `hooks/studio` or `stores/studio`: those are v2 work in progress. The exact file list is saved; I'd delete by that list, then run `npm run build` to confirm.

## 2. FIX: broken wiring found

| Problem | Fix |
|---|---|
| `main.py` crashes: `macro.py` imports the missing `app.services.macro` | Restore `app/services/macro/` from git, or remove the `macro` import and route |
| Frontend `app/monitor/` page and 3 nav links call `/api/monitor`, which is unmounted | Delete the page and its links (goes with the monitor deletion above) |
| Nav links to `/labs/pca`, but no such page exists | Remove the link (or point it at `/labs/pca-v2`) |
| `research_v2` and `ml_v2` services exist but have no mounted routes (`research_v2` has no API file) | Leave as is; you said the v2 mounting is in progress |

## 3. DECIDE: old v1 features that have a v2 replacement

These are still linked in the UI and called, so deleting them removes a working page. For each, deleting means the page + its API file + the services only it uses. Say yes or no per row.

| v1 feature | Frontend | Backend API | Services it alone uses | v2 replacement |
|---|---|---|---|---|
| Volatility lab | `app/labs/volatility/` | volatility routes in `api/labs.py` | `volatility_intelligence.py`, `regime_peak_engine.py`, `regimes_intelligence.py` | `labs/volatility-v2` |
| Factors lab | `app/labs/factors/` | factor routes in `api/labs.py` | `factors_intelligence.py`, `institutional_engine.py`, `app/factor_data.py`, `app/factors.py` | `labs/factors-v2` |
| ML lab | `app/labs/ml/` | non-v2 routes in `api/ml_api.py` | `services/ml/` (old; includes an old `ml/v2` copy) | `labs/ml-v2` + `services/ml_v2/` |
| Research lab | `app/labs/research/` | `research_beta`, `research_correlation`, `research_macro_shock`, `research_regimes`, `research_style_map`, `research_stats` | `research_math.py`, `models/research_schemas.py` | `labs/research-v2` (API not mounted yet) |
| PCA (old) | none (link dead) | `pca_eigenphysics.py`, `pca_god_mode_api.py` | `pca_features.py`, `pca_state_engine.py`, `pca_god_mode.py` | `labs/pca-v2` |
| Screener (old) | used by labs pages | `screener_api.py` | `screener_quant360.py`, `screener_evaluator.py`, `screener_state.py`, `fundamentals_cache.py`, `market_state.py`, `screener.py` | `labs/screener-v2` |
| Portfolio (old) | `app/portfolio/` | `api/portfolio.py` (106 routes) | `portfolio_*.py` (the remaining 9), `strategy_engine.py`, `strategy_research.py`, `document_summarizer.py`, `sentiment_analyzer.py` | `labs/portfolio-v2` |
| Studio v1 | `/studio` pages partly call it | `routers/studio.py` | `services/studio/` | `studio_v2` |

**Not tied to a v2 feature** (keep unless you say otherwise): markets, markets_daily, market_labs, macro, liquidity_api, research_e / research_fg (Cluster E, F+G), research_quantitative, nse_india, prices/quotes, trades, payments, sovereign, cli, alpha, options, orderbook, security, websocket, accuracy_status, strategy_institutional, historical_prices_api.

## Order of work after approval

1. Fix the backend crash (section 2, first row) so there's a working baseline.
2. Delete section 1, then run: backend `import main` plus the route list, `pytest backend/tests`, and frontend `npm run build`.
3. Delete each approved section-3 feature one at a time, rerunning the same checks after each. Anything that breaks gets fixed or restored before the next.
4. Everything stays recoverable: git-tracked files come back with `git checkout`. I'd also zip the untracked deletions to `~/Downloads/quant_cleanup_backup.zip` first.

Reply with:
- (a) approve section 1;
- (b) for the macro crash: restore from git, or remove macro;
- (c) yes or no for each section-3 row;
- (d) Studio test strategies: delete or keep?
