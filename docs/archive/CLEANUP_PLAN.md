# Repo Cleanup Plan

Written 2026-10-05. It replaces the old root `CODE_CLEANUP_PLAN.md`, most of which has already been done.

## How this was checked

- **Backend:** I traced every module reachable from `backend/main.py` by static imports. The seven V2 packages load their features dynamically, so they count as reachable. Every mounted route was matched against the URLs the frontend calls.
- **Frontend:** I traced every file reachable from `src/app/` (pages, layouts and routes), counting static imports, `import()` and `require`. Tests are excluded.
- **Not found by this scan:** something that builds a module name or URL from strings at runtime.

**Rule before each batch:** run `backend: python3.11 -c "import main"` and `pytest`, then `frontend: npm run build`. Commit each batch separately so any one can be reverted.

---

## Batch 1: safe, zero behavior change

### Repo root

| Delete | Why |
|---|---|
| `Space-Portolio-main/` (24 MB) | A separate template project; nothing references it |
| `public/` (root: `file.svg`, `globe.svg`, `next.svg`, `vercel.svg`, `window.svg`) | Leftovers from the original Next.js template; the app uses `frontend/public/` |
| `CODE_CLEANUP_PLAN.md` | Replaced by this file |
| `ULTRA_SKILLS_MANIFEST.md` | Optional; nothing references it. Keep it if you use it for skills. |

Keep root `package.json` and `package-lock.json`: `docker/Dockerfile.nse-api` uses them.

### Backend

| Delete | Why |
|---|---|
| `backend/app/studio_v2/storage/strategies/contract-handoff_*.py` (51 files) and `http-paper-route_*.py` | Strategies saved by old test runs; nothing imports them |
| `backend/app/checkpoints/checkpoint-contract-run.pkl` | Test artifact |
| `backend/app/api/demo_signals.json` | Check with `rg demo_signals` first; delete if nothing reads it |
| `backend/app/services/regime_database.db` | A stray database inside a code folder; check with `rg regime_database` first |
| `backend/backend.log`, `backend/data_cache/` | Logs and caches; recreated automatically. Add both to `.gitignore`. |
| All `__pycache__/` folders | Make sure `.gitignore` has `__pycache__/` |
| `backend/app/models/portfolio_models.py` (780 lines) | Nothing imports it |
| `backend/app/services/macro/ingestion_adapters.py` (609 lines) | Nothing imports it |
| `backend/app/studio_v2/backtest/reconciliation.py`, `factors/diagnostics.py`, `optimizer/cpcv.py`, `shared/monte_carlo.py` | Nothing imports them (Studio V2 is retired) |

### Frontend: 94 files (about 20,800 lines) that no page imports

Grouped below by folder.

| Delete | Lines |
|---|---|
| `src/components/chart_engine/`: the unused parts, which are `AlertEngine/`, `AnchoredIndicators/`, `ConfluenceEngine/`, `ExecutionQuality/`, `IndicatorTransparency/`, `MarketStructure/`, `PreTradeSanityGate/`, `ReplayEngine/`, `RiskFirstMode/`, `StrategyAutopsy/`, `VolumeProfile/`, `store/`, `LayoutSelector.tsx`, `LightweightChartCanvas/`, `MultiChartWorkspace.tsx`, `MultiChartWorkspaceV2.tsx`, `MultiPaneChart.tsx`, `Q360QuantPanel.tsx`, `SidebarWidgets.tsx`, `TradeContextOverlay.tsx`, `index.ts`, `useMultiChartWorkspace.ts`, `workspaceTypes.ts`. **Keep** `IntradayChartWrapper`, `StableChartContainer` and `q360_chart_core` (pages use them). | ~11,600 |
| `src/components/labs/EtfFactorDna.jsx`, `LiquidityIntelligenceLab.jsx`, `VolatilityLabPro.jsx`, and in `labs/v2/`: `AnomalyGravityWell`, `GalaxyStarMap`, `GalaxyStarMap2D`, `IntrinsicWarp`, `LiquidityCanyons3D`, `MonteCarloCone`, `RegimeWaves3D` | ~3,500 |
| `src/components/research/`: `ControlPanel`, `ExportButtons`, `HeatmapMatrix`, `ScatterCanvas`, `StatusMeta`, `TimeSeriesModal`, `UniversePicker` | ~1,800 |
| `src/components/monitor/` (whole folder; the Monitor page was removed) | ~1,000 |
| `src/components/ui/`: `button`, `card`, `input`, `label`, `metric-card`, `navbar`, `panel`, `select`, `table`, `tabs` (.jsx versions no page imports) | ~640 |
| `src/components/factors-v2/FactorsV2Client.jsx` | ~600 |
| `src/types/studio/*.d.ts` (9 files) | ~410 |
| `src/components/studio/shell/StudioConfirm.jsx`, `studioFeatureFlags.js`, `useUnsavedGuard.js`; `studio/visual-kernel/downsample.js`, `webgl.js`, `workerClient.js` | ~350 |
| `src/components/CommandBar.jsx`, `GamificationRibbon.jsx`, `WatchlistSelector.jsx`, `symbols/SelectedPills.jsx` | ~510 |
| `src/charts/DotGrid.tsx`, `src/charts/Gauge.tsx`, `src/lib/api/research.js`, `src/lib/theme/researchTokens.ts`, `src/stores/studio/researchJournalStore.js`, `src/types/global-css.d.ts` | ~300 |

Check `types/global-css.d.ts` last: TypeScript reads ambient `.d.ts` files without imports, so run `npm run build` after removing it.

### Frontend assets

| Delete | Why |
|---|---|
| `frontend/public/hero_quantum.mp4` (37 MB) | Nothing references it |

---

## Batch 2: dead backend APIs (routes the frontend never calls)

Remove the `include_router` line in `main.py` and the files listed. About 3,700 lines.

| Router (lines) | Also delete | Keep (still used elsewhere) |
|---|---|---|
| `api/research_e.py` (1,061) | `services/cluster_e_service.py` (358) | `fundamentals_service.py` (used by `services/ml/v2/data_loader.py`) |
| `api/research_stats.py` (792) | none | `research_math.py`, `research_data.py` |
| `api/pca_god_mode_api.py` (467) | none | `services/pca_god_mode.py` (`api/labs.py` uses it) |
| `api/quotes.py` (236) | none | `research_cache.py`, `universe.py` |
| `api/accuracy_status.py` (195) | none | `accuracy_enhancements.py` (`sentiment_analyzer.py` uses it) |
| `api/historical_prices_api.py` (163) | none | `historical_price_service.py` |
| `api/strategy_institutional.py` (95) | `services/polars_strategy_engine.py` (112) | `historical_price_service.py` |

---

## Batch 3: stale docs inside module folders

These are old self-audits, checklists and speed plans that contradict the verified reviews in `docs/reviews/`. When each module is rebuilt (`docs/reviews/V2_REBUILD_PLAYBOOK.md`), fold anything still true into its `DONE.md` and delete the rest. Each module's `docs/` spec folder stays.

| Module | Delete |
|---|---|
| `factors_v2/` | `AUDIT.md`, `FACTOR_INTELLIGENCE_COMPLETION_REPORT.md`, `FACTOR_INTELLIGENCE_DEPLOYMENT_BEYOND_PLAN.md`, `FACTOR_INTELLIGENCE_SPEED_MAX_PLAN.md`, `RUNTIME_NULL_AUDIT.json`, `review.md` |
| `ml_v2/` | `gap_classification.md`, `review.md`, `speed upgrades.md`, `upgrades.md`; empty `schemas/`, `utils/` |
| `pca_v2/` | `audit code.md`, `audit.md`, `review.md`; empty `schemas/`, `utils/` |
| `portfolio_v2/` | `NOT_DONE.md`, `docs_review.md`, `missing.md`, `review.md`, `speed upgrades.md` |
| `screener_v2/` | `FEATURES.md`, `NOT_POSSIBLE_WITH_CURRENT_DATA.md`, `missing.md`, `review.md` (Codex already has `DONE.md`) |
| `volatility_v2/` | `AUDIT.MD`, `AUDIT 2.MD`, `review.md`, `speed upgrades.md`, `speed upgrade 2 .md`, `vol frontend upgrades.md`; empty `schemas/`, `utils/` |
| `studio_v2/docs/` | All of it (Studio V2 is retired) |
| `docs/STUDIO_V2_API_INVENTORY.md`, `docs/STUDIO_V2_FRONTEND_API_TRACEABILITY.md` | Together with `backend/scripts/generate_studio_v2_api_inventory.py`, `generate_studio_v2_frontend_traceability.py` and `extract_studio_v2_frontend_calls.mjs` |

---

## Batch 4: larger refactors (plan before doing)

These need a session each, not a delete.

1. **Studio V2: 16,000 lines kept alive for two route groups.** `main.py` imports the whole `app/studio_v2/router.py` just to keep `data-studio` and `health`. Move those routes and their real dependencies into a small `app/api/data_studio.py`, then delete `app/studio_v2/` except what that needs. The observability middleware (`studio_v2/shared/observability.py`) also needs a new home. Check `frontend/src/hooks/studio/useDataStudio.js` before and after.
2. **Legacy V1 services that V2 modules replace.**
   - The partly-used V1 routers are `screener_api.py` (8 of 22 routes called), `portfolio.py` (57 of 106), `macro.py` (5 of 15), `market_labs.py` (4 of 13) and `research_quantitative.py` (4 of 15). Remove the uncalled routes first; services then become dead one at a time.
   - Files like `screener.py`, `screener_quant360.py`, `strategy_research.py` and `strategy_engine.py` are **still reached** by those V1 routers, which is why they cannot be deleted yet.
   - Decide per page whether the V1 page stays. When a V1 page is retired, its router and services go with it.
3. **Two "ML v2" trees.** `services/ml/v2/` (galaxy, warp, probability hub, state engine) and `services/ml_v2/` (the 12-feature module) both exist, and `ml_v2` features import from `ml/v2`. Fold the used parts into `ml_v2/core/` during the ML rebuild.
4. **Duplicate data loaders.** There are seven V2 `core/data_loader.py` files plus `research_data.py`, `data_engine.py` and `robust_data_fetcher.py`. Move to one shared market-data layer (Polars/DuckDB, see `docs/TECH_STACK_AND_INFRA.md`) as modules are rebuilt.
5. **Frontend pages nobody links to.** After Batch 1, list routes under `src/app/` that no navigation links to, and decide which pages to retire.

## Do not delete

- `backend/data/`, `data/`, `factors/data/`: market data used by the V2 loaders.
- `research_exports/`: your paper package. Some loaders still read a fallback parquet from it.
- `factors/`: the data pipeline that produces `factors/data/`.
- `backend/venv/` (1.1 GB): your environment. It should be in `.gitignore`, not deleted. Replace it with `uv` later.
- `docs/reviews/`, `docs/evidence/`, the `ORIGINAL_STUDIO_*` plans, `ml_final_features.md`, `RESEARCH_V3_CONTRACTS.md`, `final paper 3 .md`.

## Size of the win

| Batch | Files | Lines or size |
|---|---|---|
| 1 | about 165 | about 22,700 lines, plus 61 MB (Space-Portolio and the unused video) |
| 2 | 9 | about 3,500 lines |
| 3 | about 35 docs | n/a |
| 4 | most of `studio_v2/` and the V1 leftovers | up to 25,000+ lines |
