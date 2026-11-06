# Factors V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/factors_v2/` (spec: `docs/factors features.md` 524 lines + `factors design.md`, code: `core/analytics.py` 790 lines, `core/data_loader.py` 426 lines, `core/performance.py` 575 lines, `core/contracts.py` 138 lines, 14 feature files ~3,031 lines), `backend/app/api/factors_v2.py` (168 lines) + mount in `backend/main.py:34,129`, `frontend/src/app/labs/factors-v2/` (14 feature pages + hub), `frontend/src/components/factors-v2/` (`customPagePrimitives.jsx` 3,875 lines, `registry.js` 470 lines, `FactorsV2Client.jsx` 594 lines).

Prior audit `review.md` (578 lines, 2026-07-13) fixed real bugs (F07 Monte Carlo, F07 fabricated quintiles, F09 impact discontinuity, F02 sinusoidal/hash fakes, F01 single-factor gate, F03 annualization, predictive-regression HAC SEs). This review re-verifies each claim against current code and finds one new P0 the old audit missed: the frontend sends a raw payload body while the backend expects a `{payload}` envelope, so every UI run silently executes on defaults.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | Router is mounted but the request envelope mismatches: UI inputs are silently dropped and every run executes on defaults. |
| Data integrity | **Broken** | Latest-snapshot fundamentals feed historical sorts/backtests: look-ahead bias. No FX loader; all loaders fail silent-empty. |
| F01 Valuation spread | Partly correct | Real quintile spread + crisis anchors, but history is an FF return proxy and missing regressions get synthetic filler numbers. |
| F02 Exposure | Partly correct | Worst fakes removed; return-based leg is still a portfolio-level proxy, no CIs, no neutralization toggle. |
| F03 Attribution | Partly correct | Annualization fixed per frequency; carryover is still autocorrelation, cost model not decomposed. |
| F04 Regime | Mostly fine | Real HMM/GMM/rules composite; 3-state collapse and partial timing-signal menu. |
| F05 Decay | Mostly fine | Half-life algebra fixed and tested; acceleration test is a directional proxy. |
| F06 Crowding | Partly correct | Real 4-metric composite; equal-weight only, undocumented value-factor inversion. |
| F07 Backtest | Partly correct | Real stationary-bootstrap MC and null (not fake) quintiles; decile interpolation and a duplicate ADV-capacity formula remain. |
| F08 Covariance | Mostly fine | DCC gating fixed and reported; DCC is still local recursion, not MLE. |
| F09 Capacity | Mostly fine | Continuous impact model, tested; sensitivity table is 2 hand-picked cases. |
| F10 Optimizer | Thin | Real cvxpy QP + frontier; robust path is shrinkage, FAP is a correlation, constraints partial. |
| F11 Stress | Partly correct | Reverse-stress math correct; IRF bootstrap is a variance-scaling approximation. |
| F12 DNA | Thin | Real pipeline over F04/F05/F06/F08; axis scalings arbitrary, 3 regimes not 6, no comparison factors. |
| F13 Monitor | **Mislabeled** | "IC drift" is return autocorrelation, not cross-sectional IC; backend admits it in `meta.method`. |
| F14 Report | Thin | Assembles upstream summaries; PDF is a title + status table, no embedded charts. |
| Tests | **Thin** | No `factors_v2/tests/` dir; 5 focused math tests in `backend/tests/test_factors_v2_math.py`, no wiring/golden/integration tests. |
| Frontend | Wired but drifted | Real run flow exists (not a shell), but triple-declared contract drifts from backend, hub shows synthetic demo numbers, "dormant" labels are stale. |

Bottom line: the module *runs end to end* and the worst fabrications are gone, but no UI input currently reaches the backend (B1), historical results carry look-ahead bias (B2), and several statistics are proxies wearing spec names (F01 filler, F07 decile/ADV-capacity, F13 IC, F11 IRF bands). Fix order: repair the envelope, contain look-ahead, relabel or replace the proxies, then add wiring and golden tests.

---

## 2. Blockers (fix first)

### B1. Request-envelope mismatch: every UI run ignores user inputs
- Backend `POST /feature/{id}/run` (`api/factors_v2.py:106-108`) declares `request: FactorsV2RunRequest` with a `payload` field, then runs `_sanitize_payload(request.payload)`.
- Frontend `runFactorsV2Feature` (`frontend/src/lib/api.js:1003-1010`) posts the flat feature payload as the whole body: `body: JSON.stringify(payload)`. Pydantic parses that as `FactorsV2RunRequest(payload={})`, so `request.payload` is always `{}` and the backend runs pure defaults.
- Both live paths hit this: `FactorsV2Client.jsx:134` and `customPagePrimitives.jsx:2612-2613` (`mutationFn: (nextPayload) => runFactorsV2Feature(feature.id, nextPayload)`).
- Effect: factor selectors, windows, thresholds, AUM, shocks, and `compute_mode="research"` chosen in the UI never reach compute. Nothing errors; results just never reflect inputs.
- Fix: wrap the body as `{payload}` in `runFactorsV2Feature` (one line), and add a wiring test posting a non-default factor/window asserting it appears in `meta`/echo. Note `run-all` already sends `{payload, feature_payloads}` and matches its `Dict` handler (`api/factors_v2.py:120-121`).

### B2. Look-ahead bias in fundamentals
- `characteristic_panel` (`analytics.py:236-313`) merges `_latest_fundamentals()` (`:199-207`, latest snapshot per ticker) onto the price panel. Every cross-sectional score is today's fundamentals.
- `_real_quintile_monotonicity` (`feature_07.py:94-134`) sorts on those same current scores (`score_series` from `chars`) against historical forward returns (`fwd_returns`, `:111`). Backtested quintile returns use information not available at formation.
- `valuation_spread` history (`analytics.py:341-356,359-431`) is an FF cumulative-return proxy (`_spread_series_from_ff`), not the spec's characteristic spread history, while `current_cross_section_spread` is today's snapshot. Percentiles compare two different quantities.
- No FX loader exists (Category 10; `data_loader.py` has no FX path), so any global-universe rank mixes currency momentum in. Every loader returns empty frames on failure with no blocking error.
- Fix: point-in-time fundamentals with a reporting lag, or gate historical features to price-only factors and label FF-proxy history as such in `meta` and the UI. Minimum honest step: surface `data_through`/snapshot-date and a look-ahead warning on F01/F05/F07 outputs until PIT exists.

### B3. Stale "dormant" claims and synthetic hub numbers
- Router IS mounted (`backend/main.py:34` import, `:129` `include_router(factors_v2.router, prefix="/api")`, routes resolve at `/api/labs/factors/v2`). The old "unmounted" finding is stale, but the stale text lives on: `api.js:985` ("Dormant until ... wired"), `FactorsV2Client.jsx:79-82` ("dormant compute kernel") and `:179` (`api: dormant` badge), `feature_01.py:82` (`alert_delivery: ... remains dormant`), `feature_13.py:90`, `api/factors_v2.py:86,166`.
- Hub `app/labs/factors-v2/page.js:62-117` renders hardcoded demo series (`pctWave`, fixed gauge values 23/81/67/44, fixed crowding 73, fabricated equity/capacity/frontier arrays) that never come from the backend, beside live localStorage badges. A reader cannot tell demo from data.
- Fix: delete dormant strings now that the router is mounted; gate hub visuals on real `latest-summary` runs or label the block "illustrative".

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = stand-in, labeled or not; MISSING = not present; FIXED = old-audit bug verified gone.

### F01 Valuation spread (`feature_01.py:17-135`, `analytics.py:359-474`)
| Spec item | State | Detail |
|---|---|---|
| Single-factor query | FIXED | Old `len(...) <= 1` overwrite is gone (`:20` now `if not requested_factors`). |
| Per-factor sector table | FIXED | `:68-69` now fans out per factor, not `rows[0]` for all. |
| HAC SEs in predictive regression | FIXED | Newey-West HAC with `lag ~ horizon^0.25` (`analytics.py:450-473`), covered by `test_predictive_regression_uses_hac_standard_error`. |
| Spread history | PROXY | 252d rolling sum of the mapped FF column (`analytics.py:341-356`), not characteristic-spread history. |
| Missing-data fillers | WRONG | `_complete_valuation_row` (`:96-110`): percentile defaults to 50.0, beta to -0.002, R-squared to 0.18, expected return to `(50-pct)/100*0.20`. Synthetic numbers presented beside real regressions with no flag. |
| Expected-return CI keys | OK | `:59-60` now reads `ci_90_low/ci_90_high` matching `predictive_regression` output. |
| Crisis anchors | OK | 4 events, nearest-available-date logic (`:113-135`). |
| Universe filter, custom factors, display mode, email delivery | MISSING | Frontend `FEATURE_INPUT_SPEC_UPGRADES["01"]` exposes `universe_filter/sector_filter/display_mode` the backend ignores. |

### F02 Exposure (`feature_02.py:12-254`)
| Spec item | State | Detail |
|---|---|---|
| Sinusoidal rolling exposures / hash exposures | FIXED | Gone. No-history returns `{"snapshots": []}` (`:135-137`); unknown tickers get `unavailable_missing_characteristics` with null exposure (`:252-253`). |
| Return-based exposure | PROXY (labeled) | Portfolio-level OLS via `_portfolio_return_history` (`:120-132`), not per-stock time-series OLS as spec'd. `meta.methodologies` honestly says `return_based_proxy`. |
| 95% CIs, sector-neutral toggle, benchmark-relative active exposure | MISSING | SEs returned, no bands; `neutralization` input ignored. |
| Auto holdings `head(30)` | WRONG-ish | `:20` still samples arbitrary first-30 tickers when holdings omitted. Acceptable as an explicit sample only if labeled; currently silent. |

### F03 Attribution (`feature_03.py`)
| Spec item | State | Detail |
|---|---|---|
| Annualization | FIXED | Per-frequency factor (`:41-43`: weekly 52, monthly 12, quarterly 4, else 252). |
| Carryover | PROXY (labeled) | `_carryover_proxy_fallback` autocorrelation (`:160-168`), method string says proxy. |
| Transaction-cost decomposition, holdings interpolation, benchmark-relative Brinson | MISSING | Cost model never read from payload; equal-weight exposures default persists. |

### F04 Regime (`feature_04.py:31-58,286`)
| Spec item | State | Detail |
|---|---|---|
| HMM/GMM/rules composite, transition matrix, timing regression | OK | Real fits; GMM correctly gated to research/cached. |
| 4-state spec model | PROXY | Collapsed to 3 labels (expansion/transition/stress). |
| Timing signals, momentum params, significance toggle | Partial | Stress/momentum/vol only; no valuation-spread or crowding inputs; fixed 63d momentum lookback. |

### F05 Decay (`feature_05.py`, tested)
| Spec item | State | Detail |
|---|---|---|
| Linear half-life algebra | FIXED | Solves fitted curve (`:294`), pinned by `test_linear_half_life_solves_fitted_curve` (25.5). |
| Bootstrap half-life CI | OK | Parametric refit bootstrap (`:122-146`); normal-approx fallback only when no successful refits. |
| Post-2015 acceleration "significance" | PROXY (labeled) | Directional half-life change, method string says `significance proxy` (`:337`). |
| Pearson / beta-neutral IC, full-horizon rolling fits | Partial | Spearman + sector-neutral proxies present (`:217-218`); multi-factor radar uses best-R-squared fit (`:274`). |

### F06 Crowding (`feature_06.py:36-101`)
| Spec item | State | Detail |
|---|---|---|
| 4-metric composite, league, scatter, deleveraging score | OK | Real Roll/Amihud local proxy, HHI, autocorrelation, spread percentile. |
| Composite method | MISSING | Equal-weight only; frontend advertises `weighted_zscore/percentile_average/bayesian` (`registry.js:295`) the backend ignores. |
| Value/quality inversion | WRONG-ish | `:36` inverts spread percentile for value/quality/profitability with no documented justification. |
| Crash credible interval | WRONG label | Beta quantiles use 0.05/0.95 (90% interval) in a field set that mixes 95% conventions; pick one and label it. |

### F07 Backtest (`feature_07.py`, tested)
| Spec item | State | Detail |
|---|---|---|
| Monte Carlo | FIXED | Stationary block bootstrap (`:168-185`), pinned by `test_monte_carlo_uses_resampled_paths`. |
| Empty quintiles | FIXED | Nulls + `unavailable_no_fabrication` (`:137-149`), pinned by `test_missing_quintiles_are_not_fabricated`. |
| Quintile formation timing | OK | Next-session formation via `shift(-(rebalance+1))/shift(-1)` (`:111`); scores still carry B2 look-ahead. |
| Decile table | PROXY (labeled) | Linear interpolation from quintiles (`:152-165`), method string says so. Not measured deciles. |
| `_adv_capacity_curve` | PROXY + duplicate | `:237-268` uses magic `12.0*sqrt(participation)*252/21` disconnected from `implementation_shortfall_kernel`. Second capacity math inside the backtest feature; remove or reconcile with F09. |
| Multi-factor composite, periodic rebalancing, short toggle, benchmark | MISSING | Single-factor, single-formation portfolio; walk-forward is a single-factor proxy (labeled, `:222-234`). |

### F08 Covariance (`feature_08.py:18-96`, `analytics.py:497-561`)
| Spec item | State | Detail |
|---|---|---|
| DCC dead-code override | FIXED | Old always-off override is gone; `:19-32` gates by count/mode and reports `requested_method/used_method/dcc_allowed` in `matrix_validation` (`:86`). |
| DCC estimator | PROXY (labeled) | EWMA-vol + Engle recursion (`dcc_garch_payload`), no MLE; meta says "local ... recursion". |
| Estimation window | Partial | `window_days` now threads into the sample path (`:23,33`); core still tails at 1260 (`analytics.py:498`). |

### F09 Capacity (`feature_09.py`, tested)
| Spec item | State | Detail |
|---|---|---|
| Impact discontinuity at $100M | FIXED | Single continuous square-root model (`:84-94`), pinned by `test_capacity_impact_is_continuous_and_liquidation_uses_turnover`. |
| TTL formula | FIXED | Now turnover-based (`:98`). Memo text (`:48`) still narrates the old Kyle-below/Almgren-above split; update the string. |
| Sensitivity analysis | PROXY | Two hand-scaled cases (`:54`: x1.67, /2), not a recomputed sweep. |
| Allocator memo | Thin | One plain-text paragraph (`:48`), not a formatted one-pager. |

### F10 Optimizer (`feature_10.py:19-38,87`)
| Spec item | State | Detail |
|---|---|---|
| Core QP, frontier, BL posterior, cardinality post-processing | OK | Real cvxpy solve with OSQP/CLARABEL fallback. |
| Robust N>100 path | PROXY (labeled) | Expected-return shrinkage approximation (`:32-38`); honest but not robust optimization. |
| FAP diagnostic | WRONG | Pairwise correlation (`corrcoef` of alpha vs mu), not a regression of alpha on the risk model. |
| Manual ER, F04 alphas, gross/net/sector/turnover/TE constraints, 50-pt frontier | MISSING | Frontier is 25 points; warm-start cache keyed on `hash(tuple(names))` risks collisions. |

### F11 Stress (`feature_11.py:25,110-189`)
| Spec item | State | Detail |
|---|---|---|
| Reverse-stress vector | OK | Closed-form minimum-norm solution under the covariance metric. |
| IRF confidence bands | PROXY | Fixed-design variance rescaling (`:110-129`), not a VAR-coefficient bootstrap; comment admits the shortcut. Only the horizon-21 slice is exported as the contagion output. |
| Preset library, macro-linked scenarios, nonlinear propagation, F02 import | MISSING / Partial | 4 presets; Mahalanobis analog on factor returns, not macro; exposures manual via payload. |

### F12 DNA (`feature_12.py:34-39,163,209`)
| Spec item | State | Detail |
|---|---|---|
| Pipeline (F04/F05/F06/F08 + purity + classifier) | OK | Real orchestration; expensive (4 upstream runs) but correct. |
| Radar axis scalings | PROXY | Hard constants (`IC*1000`, `100-half/5`, `100-HHI*500`); reasonable but arbitrary and undocumented. |
| 6 macro regimes, comparison factors, period focus, user labels | MISSING | 3 regimes; `analysis_depth`/`period_focus` accepted but unused. |

### F13 Monitor (`feature_13.py:33-90,126-146`)
| Spec item | State | Detail |
|---|---|---|
| "IC drift" | WRONG (admitted) | `:33-37` correlate factor returns with their own 21d-forward shift: return autocorrelation, i.e. the F06 metric, not cross-sectional rank IC. `meta.method` (`:87`) confesses; the UI labels (`registry.js`, hub "Daily IC drift z-score") do not. Relabel to "persistence drift" or compute true IC from stored PIT snapshots. |
| IC threshold default | OK backend / drifted frontend | Backend `-1.5` (`:55`) matches spec; frontend default is `-1.0` (`registry.js:186`). |
| Chow diagnostic | PROXY (labeled) | Two-sample mean-shift F (`:126-146`), `diagnostic: weekly_chow_mean_shift_proxy`. Not a Chow coefficient test. |
| Recovery tracker, email/webhook delivery | MISSING | Resolution metadata only (`:76`); channels listed as configurable/beta (`:70-75`) with no worker. |

### F14 Report (`feature_14.py:31-199`)
| Spec item | State | Detail |
|---|---|---|
| Assembly, DDQ map, HTML, page-cap deferral, contact/disclaimer | OK | Present, including deferred-async path (`:86-99`) and contact/disclaimer rendering (`:189-194`, closing a prior gap). |
| PDF content | Thin | Title + section/status/summary table + per-section paragraphs + JSON audit dump (`:153-199`). No embedded charts (meta `:132` confirms rasterization is "frontend/export worker concern"); audit is a JSON code block, not investor prose. |
| Silent degradation | WRONG-ish | Upstream failures become "Section unavailable" (`:66-68,77-79`) with `status: ok` overall. A report with failed sections should be `warning`/`partial`. |
| Fragment cache | Leak | `_SECTION_FRAGMENT_CACHE` (`:16`) is unbounded in a long-lived server process. |

---

## 4. Use open source that is already installed

Verified importable from the code read (not assumed):

| Hand-rolled today | Replace with | Why |
|---|---|---|
| HAC SEs in `predictive_regression` (`analytics.py:450-473`, hand-rolled Bartlett loop) | `statsmodels.stats.sandwich_covariance.cov_hac` | Tested kernel, automatic lag selection; deletes ~25 lines of bespoke code. |
| Chow-mean-shift proxy (`feature_13.py:126-146`), no break p-values anywhere | `statsmodels.stats.diagnostic.breaks_cusumolsresid` + an Andrews (1993) critical-value table | Gives the missing structural-break p-value/CI the spec asks F05/F13 for. |
| VAR lag select + IRF bands (`feature_11.py`) | keep `statsmodels.tsa` but bootstrap coefficients properly (fixed-design residual resample with refit on the small factor panel) | Removes the variance-rescaling approximation; panel is tiny so refit is cheap. |
| DCC recursion (`analytics.py:529-561`) | keep local recursion for realtime, verify Research path against `arch` DCC if `arch` is installed; otherwise keep labeled | MLE per request is disproportionate; the ask is a documented accuracy bound, not a rewrite. |
| Quintile/decile sort inference (`feature_07.py:94-165`) | `arch.bootstrap.StationaryBootstrap` / `MovingBlockBootstrap` over the quintile-spread series | Block bootstrap CIs for monotonicity instead of interpolated deciles. |
| Half-life CI (`feature_05.py:122-146`) | keep parametric refit, or `arch.bootstrap.MovingBlockBootstrap` on the IC series | Matches the spec's block-bootstrap requirement. |
| GMM/HMM/GaussianMixture/Roll/Amihud | keep `sklearn` + `hmmlearn` (already imported and used) | No change needed; already the right tools. |

Needs approval (verify installed first; do not add blindly):

| Library | For | Notes |
|---|---|---|
| `linearmodels` | Panel OLS/FE, clustered/DK SEs, real Hausman (F02/F03 upgrades) | Only if panel regressions graduate beyond `ols_beta`. |
| `pyfixest` | Any future causal extension | No causal feature exists in Factors V2; do not add preemptively. |

Frontend: `@tanstack/react-query` is already used (`customPagePrimitives.jsx:4,2612`); keep it. Charts: `recharts` is the de facto standard in both factors-v2 components; `d3` is imported only by the hub page (`page.js:4`) for static demo visuals, remove that import with the B3 cleanup.

---

## 5. Frontend review

- **Run flow is real (not a shell)**. All 14 feature pages render `<CustomFeaturePage featureId="XX" sections={...}/>` with `useMutation` + `runFactorsV2Feature`, loading/error/empty states, comparison mode, output profiles, and annotations (`customPagePrimitives.jsx:2571-2622,2776-2788,2897-2928`). This supersedes the old "Run does nothing" finding, which described a different component generation.
- **B1 makes the flow cosmetic**: because the envelope drops inputs, Run always computes defaults. The UI also gives no hint of this; it reports success.
- **Duplicated contract, three layers deep**: backend `FEATURE_CONTRACTS` (`contracts.py:40-138`) vs `FACTORS_V2_FEATURES` + `FEATURE_INPUT_SPEC_DEFAULTS` + `FEATURE_INPUT_SPEC_UPGRADES` (`registry.js:1-382`). Drift already exists: frontend-only inputs the backend ignores (`universe_filter`, `display_mode`, `composite_method` options, `dcc_garch` where gated, `alert_preferences` email/slack, F13 threshold -1.0 vs backend -1.5). Fix: fetch `GET /features` and render from it; keep only presentation hints (chart type, rank) locally.
- **Two parallel renderers**: `FactorsV2Client.jsx` (generic `FactorsV2FeaturePage`, labeled dormant, apparently unlinked from the `feature-XX` routes which all use `CustomFeaturePage`) vs `customPagePrimitives.jsx` (3,875 lines: workbench, config curtain, 20+ chart renderers, annotations, profiles, comparison). Pick one path; the feature routes use the latter.
- **Misleading options**: F13 threshold default, F08 `dcc_garch` where locally recursed, F14 `chart_theme/chart_palette` with no backend styling effect (`feature_14.py` has no theme handling), F06 `composite_method`/`metric_weights`, F02 `neutralization`/`exposure_methodology`.
- **No upload path**: holdings are inline JSON textareas; F14 `logo_path` is a *server path* (`feature_14.py:162-168`) a browser user cannot supply. Needs an upload endpoint with an id reference (same ask as the research review).
- **Hub is demo, not data** (B3): synthetic series with live badges beside them; `localStorage latest-summary` coupling between hub ticker and feature runs is fragile (stale "Just now"/"Never run" across devices, no versioning).
- **Long-job UX**: no cancel, no progress, no timeout messaging for F12/F14-class runs; `run-all` (14 features incl. HMM/VAR/PDF) has no frontend entry point at all.

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

- **Envelope convention is load-bearing and untested**: Factors V2 wraps inputs as `{payload}` (`api/factors_v2.py:24-25,106-108`) while the only caller sends them flat. If sibling V2 routers use different conventions, every frontend client must be checked against its router; add a per-module wiring test asserting a non-default input round-trips.
- **Silent-empty loaders**: every `data_loader.py` failure path returns `pd.DataFrame()`; AQR/macro missing files degrade to warnings deep inside features. Fail closed on unknown tickers/symbols (422 with the missing names) and surface `data_through`/row counts in `meta` instead of burying them.
- **Stale status strings**: "dormant" appears in code, comments, UI badges, and response `meta` after the condition cleared. Status claims should derive from a health check, not string constants.
- **Spec-frontend drift**: `registry.js` encodes spec aspirations (email/slack alerts, PCA composite, DCC, custom factors) as if they were backend inputs. Frontend must not offer what the router ignores.
- **Prior-audit hygiene held**: master duplicate deleted, `features/__init__.py` exists, fakes converted to nulls/labeled proxies with regression tests. The remaining proxies are at least mostly labeled in `meta.method`; the gap is that UI labels and section titles still use spec names (IC, decile, Chow, DCC-GARCH, allocator memo).

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | Wrap `{payload}` in `runFactorsV2Feature` (`api.js:1003-1010`); add round-trip wiring test per feature (non-default input appears in output/meta) | S |
| 2 | Data integrity | PIT fundamentals or price-only gating + look-ahead warning in F01/F05/F07 meta and UI; 422 on unknown tickers; FX gap disclosed on global universe | M |
| 3 | Correctness (proxies) | Delete F01 synthetic fillers (null + flag instead of 50.0/-0.002/0.18/formula); remove F07 `_adv_capacity_curve` duplicate; relabel F13 IC to persistence drift; F10 FAP as regression; F06 inversion documented or removed; F14 failed-section status to warning/partial | M |
| 4 | Correctness (estimators) | `statsmodels` HAC/Chow/break p-values; proper VAR-coefficient IRF bootstrap; block-bootstrap quintile CIs; measured deciles or drop the table | M |
| 5 | Tests | Wiring/envelope tests; golden-number tests per estimator on fixed fixtures; look-ahead guard test (scores shifted → results change); silent-fallback test (unknown ticker → 422) | M |
| 6 | Frontend | Manifest-driven inputs from `GET /features`; remove dormant strings; gate or label hub demo visuals; uploads for holdings/logo; cancel/progress on long runs; expose `run-all` as async job | M |
| 7 | Cleanup | Bound `_SECTION_FRAGMENT_CACHE` (LRU); fix F09 memo text; `hash(tuple(names))` warm-start key; drop `d3` hub import; update completion report to match this review | S |

Recommended next step: items 1 and 2 together, plus A1-A3 from the addendum, (small, and they make the module both controllable and honest), then 3 with tests from 5 alongside.

(End of file)

---

## 8. Addendum (verified 2026-10-03)

These came from a second read of the code and were not in the first pass. Read [V2_REBUILD_PLAYBOOK.md](V2_REBUILD_PLAYBOOK.md) before fixing; frontend work (section 5, item 6) is reserved for Claude. B1 is still open as of this date (`api.js:1003-1010` posts the flat payload).

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | Universe look-ahead | The research universe is the top-N tickers by **today's** dollar volume, applied to the whole history. That selects names that survived and became liquid, so every historical sort, backtest and capacity number is survivorship- and look-ahead-biased. Select at each formation date from data available then. | `analytics.py:216-225`, `data_loader.py:415-421` |
| A2 | No ticker parsing | There is no `parse_symbols` at all: user tickers are not validated, and the universe is only `max_tickers` of the top-liquidity list. Add strict parsing with a 422 listing unknown tickers. | `core/` |
| A3 | Fake zero returns | `load_market_return_matrix` fills missing returns with `0.0` before backtests and capacity jobs. Missing is not zero; it shrinks volatility and inflates Sharpe. Keep NaN and handle explicitly. | `data_loader.py:424` |
| A4 | Errors | `/feature/{id}/run` turns every exception, including bad input, into a generic 500 (`except Exception`). Map `ValueError`/`TypeError` to 422 with the message, unknown feature to 404. There are 30 more `except Exception` blocks in `core/` and `features/`. | `api/factors_v2.py:106-115` |
| A5 | Caches | `_PRICE_SAMPLE_CACHE` is unbounded and never invalidated, so a data refresh is invisible until restart. `_CHAR_PANEL_CACHE` evicts FIFO, not LRU. Key both on the parquet `mtime` (Screener V2 pattern). | `analytics.py:213-232,310` |
| A6 | API | All runs are synchronous; `/run-all` runs 14 features (HMM, VAR, PDF) in one request with no job, progress or cancel. Use the Studio `JobStore` pattern. | `api/factors_v2.py:118-125` |
| A7 | Structure | 14 feature files around 3,000 lines with shared logic duplicated across them, plus stale `review.md` and completion reports. Consolidate shared estimators in `core/` per the playbook and record file fates in `DONE.md`. | `factors_v2/` |

## Backend rebuild status, 2026-10-07

The Factors backend was rebuilt against this review and the current playbook. B1 now has exact envelope validation and UI job wiring; B2 uses dated formation selection and lagged observed statements with explicit vintage limitations; B3's fabricated hub results were removed. A1–A7 have strict symbols, missing-return preservation, explicit input/status errors, versioned bounded caches, local durable jobs, lazy dispatch, focused estimator modules, and a file-fate record.

Per-feature corrections and removals are recorded in [Factors V2 DONE.md](../../backend/app/services/factors_v2/DONE.md). All 14 supported backend feature paths are tested. Unsupported spec claims are not treated as implemented: statistical regimes are not named macro regimes, EWMA/DCC is not MLE GARCH, fixed composite weights are not adaptive walk-forward optimization, observed volatility is not institutional crowding, and absent academic labels do not produce classifier probabilities. True cross-sectional IC, actual stock execution/bins, constrained robust optimization, refitted VAR bootstrap, in-app recovery events, and source-backed PDF sections replace the earlier proxies.

Frontend forms/renderers/layout and full browser completion remain Claude-owned. Unsupported old frontend parameters now fail with 422 instead of silently running defaults. `DONE.md` lists all limitations and exact checks; this note does not certify the original full frontend/spec as 100% delivered.
