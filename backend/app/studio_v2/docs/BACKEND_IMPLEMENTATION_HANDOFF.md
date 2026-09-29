# Studio V2 Backend Implementation and Next-Steps Handoff

**Status:** Backend contract implemented and verified  
**Primary contract:** `STUDIO_V2_API_ROUTES.md`  
**API namespace:** `/api/v2`  
**Last implementation pass:** July 28, 2026

## 1. Purpose

This document records what was implemented for Studio V2, how the pieces fit together, what was verified, and what should be done next. It is intended to prevent the next implementation pass from rediscovering architecture or replacing working services with placeholders.

The backend work described in `STUDIO_V2_API_ROUTES.md` is complete. The next major phase is frontend integration, followed by production hardening, data-provider configuration, and load testing.

## 2. Completion Summary

- All 57 newly documented HTTP and WebSocket route-and-method combinations are registered.
- The Studio V2 router is mounted by the main FastAPI application.
- All new APIs are available under `/api/v2`.
- Durable SQLite storage is shared by strategies, snippets, compositions, backtest results, collaboration metadata, governance records, alerts, journal entries, and other Studio V2 services.
- Long-running Algorithm Lab execution runs in a separate operating-system process and can be terminated through the compute-budget endpoints.
- Backtests, portfolio backtests, scenarios, attribution, tax accounting, slippage analysis, robustness tests, factor tools, optimizer extensions, data tools, and portfolio-risk services contain real implementations rather than constant or fabricated responses.
- The API contract, core quantitative invariants, importability, and OpenAPI generation were verified.
- A completion checklist was added to the top of `STUDIO_V2_API_ROUTES.md`.

## 3. Application Integration

The Studio V2 router is defined in:

```text
backend/app/studio_v2/router.py
```

It is mounted in:

```text
backend/main.py
```

The router already contains complete paths such as `/api/v2/backtest/run`. It must therefore remain mounted without an additional prefix:

```python
from app.studio_v2.router import router as studio_v2_router

app.include_router(studio_v2_router)
```

Do not mount it with `prefix="/api"` because that would incorrectly produce `/api/api/v2/...`.

## 4. Shared Architecture

### 4.1 Persistence

`shared/persistence.py` provides a thread-safe SQLite document store with:

- WAL mode
- transactional writes
- namespaced records
- durable timestamps
- indexed namespace and update-time lookups
- create-only protection
- CRUD and paginated listing

The default database is created at:

```text
backend/app/studio_v2/storage/studio_v2.sqlite3
```

Production deployments should set `STUDIO_V2_DB_PATH` to a persistent volume outside the source tree.

Model-lineage metadata is persisted separately as `lineage.json` beside the configured database. A future database migration can move lineage records into PostgreSQL without changing route semantics.

### 4.2 Strategy Repository

`algorithm_lab/repository.py` stores strategy metadata and creates real Python strategy files. Each record includes:

- strategy ID
- name
- file path
- source code
- source hash
- default configuration
- template or user metadata

Template forks, composition execution, scenario replay, standalone export, and robustness auditing all use this repository.

### 4.3 Backtest Result Repository

`backtest/repository.py` persists complete results instead of storing only summary metrics. Stored artifacts include:

- trade log
- order log
- position history
- daily returns
- daily net asset value
- warnings
- configuration
- tax report, when enabled
- portfolio-level component output, when applicable

This repository is the source for result, metrics, comparison, attribution, slippage, tax, and portfolio-result APIs.

## 5. Algorithm Lab Work Completed

### 5.1 Executable Strategy Templates

Seven executable templates were added under `data/templates/`:

1. Cross-sectional momentum
2. Time-series momentum
3. Pairs mean reversion
4. Single-name cross-sectional mean reversion
5. Principal component analysis statistical arbitrage
6. Volatility carry
7. Composite factor tilt

Every template exposes `generate_signals(data, config)`, includes a default configuration, and declares `STUDIO_INPUT = "wide_close"`. The event-driven engine recognizes this input declaration and pivots long-form OHLCV data into a date-by-ticker close matrix.

Implemented routes:

- `GET /api/v2/algorithm-lab/templates`
- `GET /api/v2/algorithm-lab/templates/{id}`
- `POST /api/v2/algorithm-lab/templates/{id}/fork`

### 5.2 Portfolio Composition

`algorithm_lab/portfolio_composer.py` supports:

- 2 to 10 unique strategies
- equal weighting
- inverse-volatility risk parity
- validated custom weights
- restricted custom Python allocation functions
- isolated strategy namespaces
- individual signal, position, and return output
- combined positions, returns, equity, and allocation output
- durable composition and execution records

Implemented routes:

- `POST /api/v2/algorithm-lab/compose`
- `GET /api/v2/algorithm-lab/compose/{id}`
- `POST /api/v2/algorithm-lab/compose/{id}/execute`

### 5.3 Standalone Production Export

`algorithm_lab/exporter.py` uses Python abstract syntax tree analysis to retain only code reachable from the signal-generation entry point. It rejects unsupported dependencies and produces a ZIP containing:

- `strategy_module.py`
- `requirements.txt`
- `README.md`

Implemented route:

- `POST /api/v2/algorithm-lab/export/{strategy_id}`

### 5.4 Collaborative Sessions

`algorithm_lab/collaboration.py` implements:

- expiring cryptographically random invite tokens
- hashed token persistence
- read and edit roles
- participant state
- cursor updates
- WebSocket snapshots and broadcasts
- read-only edit and execution enforcement
- join and leave notifications

Implemented routes:

- `WS /api/v2/algorithm-lab/session/{session_id}/collaborate`
- `POST /api/v2/algorithm-lab/session/{session_id}/invite`
- `GET /api/v2/algorithm-lab/session/{session_id}/participants`

### 5.5 Compute Guardrails

`algorithm_lab/compute_budget.py` and `algorithm_lab/execution_worker.py` implement:

- per-session running-job limits
- queued-job status
- elapsed-time tracking
- configurable warning thresholds
- recent-job history
- isolated process execution
- `SIGTERM` termination
- `SIGKILL` escalation
- kill-one and kill-all behavior
- safe transfer of serializable namespace values back into the persistent kernel

Implemented routes:

- `GET /api/v2/algorithm-lab/session/{session_id}/compute-status`
- `POST /api/v2/algorithm-lab/session/{session_id}/kill/{job_id}`
- `POST /api/v2/algorithm-lab/session/{session_id}/kill-all`

### 5.6 Snippet Library

`algorithm_lab/snippets.py` provides durable create, read, update, delete, and tag filtering.

Implemented routes:

- `GET /api/v2/algorithm-lab/snippets`
- `POST /api/v2/algorithm-lab/snippets`
- `PUT /api/v2/algorithm-lab/snippets/{id}`
- `DELETE /api/v2/algorithm-lab/snippets/{id}`

## 6. Backtest Studio Work Completed

### 6.1 Event-Driven Engine Integration

`backtest/engine.py` now supports:

- long-form OHLCV strategies
- wide close-matrix templates
- per-run parameter dictionaries
- scenario date overrides
- tax configuration
- complete tax reports on simulation results
- next-open fills
- liquidity-aware partial fills
- configurable costs
- corporate actions
- short-borrow checks

### 6.2 Portfolio Backtesting

`backtest/portfolio_engine.py` runs 2 to 10 strategies, aligns their return series, applies equal, risk-parity, or custom weights, and returns:

- individual strategy results
- strategy returns
- portfolio returns
- equity curve
- return contributions
- portfolio metrics

Implemented routes:

- `POST /api/v2/backtest/portfolio-run`
- `GET /api/v2/backtest/portfolio-result/{run_id}`

### 6.3 Attribution

`backtest/attribution.py` implements:

- Brinson-Fachler allocation effect
- selection effect
- interaction effect
- active-return reconciliation
- ordinary least-squares factor exposure attribution
- alpha and coefficient-of-determination output

Implemented route:

- `GET /api/v2/backtest/attribution/{run_id}`

Attribution requires the run to contain attribution inputs or stored contribution data. The API intentionally returns an explicit validation error instead of inventing unavailable sector classifications.

### 6.4 Slippage Audit

`backtest/slippage_audit.py` compares modeled fills to historical reference bars. It uses bid and ask data when available. If quotes are absent, it uses an explicitly labeled bar-range proxy rather than pretending that proxy values are observed spreads.

Implemented route:

- `GET /api/v2/backtest/slippage-audit/{run_id}`

### 6.5 Tax-Aware Backtesting

`backtest/tax_engine.py` implements:

- FIFO lot matching
- long and short inventory
- short-term and long-term classification
- configurable tax rates
- realized gains and losses
- wash-sale detection
- disallowed-loss reporting
- effective tax rate
- cumulative tax liabilities
- post-tax equity curves

Implemented routes:

- `POST /api/v2/backtest/run`
- `GET /api/v2/backtest/tax-report/{run_id}`

### 6.6 Scenario Replay

`backtest/scenarios.py` contains the named historical scenarios defined by the API contract. Replays use the actual event-driven engine and persist:

- equity curve
- maximum drawdown
- recovery duration
- metrics
- warnings

Implemented routes:

- `GET /api/v2/backtest/scenarios`
- `POST /api/v2/backtest/scenarios/{scenario_id}/replay/{strategy_id}`
- `GET /api/v2/backtest/scenarios/result/{run_id}`

### 6.7 Strategy Comparison

The comparison handler loads persisted run results and returns:

- complete compared runs
- a metric-comparison table
- the best run for every numeric metric

Implemented route:

- `POST /api/v2/backtest/compare`

## 7. Robustness Lab Work Completed

### 7.1 Data-Source Robustness

`robustness/data_source_test.py` aligns multiple vendors and measures:

- overlapping observations
- return correlation
- mean absolute drift in basis points
- directional agreement
- tolerance pass or failure

### 7.2 Signed Audit Trail

`robustness/audit_trail.py` generates:

- source SHA-256 hashes
- hash-chained records
- HMAC signatures
- persisted linter findings
- verification support

Set `STUDIO_V2_AUDIT_KEY` to a secret supplied by the deployment environment. Do not use the development fallback in production.

### 7.3 Parameter Interaction

`robustness/parameter_interaction.py` evaluates factorial parameter surfaces and estimates pairwise non-additive interaction strength.

### 7.4 Adversarial Stress Testing

`robustness/adversarial.py` implements deterministic variants for:

- flash crashes
- volatility clustering
- liquidity gaps
- serial reversal

Results are persisted and reproducible by seed.

Implemented routes:

- `POST /api/v2/robustness/run-core-tests`
- `POST /api/v2/robustness/audit-trail/{strategy_id}`
- `POST /api/v2/robustness/adversarial`
- `GET /api/v2/robustness/adversarial/result/{run_id}`

## 8. Factor Sandbox Work Completed

### 8.1 Composite Factors

`factors/composite_combiner.py` implements:

- winsorization
- z-score or rank normalization
- signed gross-normalized weights
- coverage output
- composite-score construction

### 8.2 Turnover and Decay

`factors/turnover_estimator.py` computes:

- daily rank turnover
- annualized turnover
- estimated annual trading cost
- information-coefficient decay by horizon
- a cost-aware recommended rebalance horizon

### 8.3 Governance

`factors/governance.py` persists:

- immutable expression hashes
- sequential versions
- draft, approved, and deprecated states
- author and reviewer actions
- required deprecation reasons
- complete change history

Implemented routes:

- `POST /api/v2/factors/evaluate`
- `GET /api/v2/factors/ic-diagnostics`
- `GET /api/v2/factors/library/{id}/versions`
- `POST /api/v2/factors/library/{id}/approve`
- `POST /api/v2/factors/library/{id}/deprecate`
- `GET /api/v2/factors/library/{id}/changelog`

## 9. Optimizer Work Completed

### 9.1 Multi-Objective Pareto Frontier

`optimizer/multi_objective.py` performs non-dominated sorting for arbitrary maximize and minimize objectives.

### 9.2 Parameter Ensembles

`optimizer/ensemble.py` supports:

- equal weighting
- objective-proportional weighting
- inverse-return-variance weighting
- numeric parameter averaging
- categorical selection
- full ensemble-member output

### 9.3 Cross-Validation

`optimizer/cross_validation.py` implements time-series folds with:

- training and test separation
- purge windows
- embargo windows
- per-fold scores
- aggregate mean and dispersion

Implemented routes:

- `POST /api/v2/optimizer/bayesian-search`
- `POST /api/v2/optimizer/ensemble`
- `POST /api/v2/optimizer/cross-validate`

## 10. Data Studio Work Completed

### 10.1 Multi-Asset Support

`data_studio/multi_asset.py` defines normalized schemas for:

- equities
- exchange-traded funds
- futures
- foreign exchange
- cryptocurrency
- fixed income
- commodities

It validates required currency, multiplier, expiry, and instrument metadata.

### 10.2 Corporate Events

`data_studio/event_calendar.py` provides persistent event records with ticker, date-range, and event-type filtering.

### 10.3 Synthetic Data Flagging

`data_studio/synthetic_flagging.py` reports:

- explicit synthetic flags
- imputed, interpolated, or backfilled sources
- suspicious repeated prices with zero volume
- contiguous affected ranges
- affected-observation counts
- synthetic fractions

Implemented routes:

- `GET /api/v2/data-studio/asset-classes`
- `GET /api/v2/data-studio/events/{ticker}`
- `GET /api/v2/data-studio/synthetic-ranges/{ticker}`

## 11. Portfolio Risk Page Backend Completed

### 11.1 Value at Risk

`portfolio_risk/var_engine.py` provides:

- historical value at risk
- historical conditional value at risk
- parametric value at risk
- configurable confidence
- configurable horizon
- portfolio-value scaling

### 11.2 Correlation and Concentration

`portfolio_risk/concentration.py` provides:

- correlation matrices
- annualized portfolio volatility
- marginal risk
- component risk
- component-risk percentages
- Herfindahl-Hirschman concentration
- effective number of positions
- largest absolute weight

### 11.3 Limits and Breaches

`portfolio_risk/limits.py` provides:

- durable risk limits
- maximum and minimum operators
- enabled states
- severities
- complete replacement updates
- breach evaluation against current metrics

### 11.4 Alerts

`portfolio_risk/alert_feed.py` provides:

- durable alerts
- fingerprint-based deduplication
- unacknowledged filtering
- acknowledgement actor and time

Implemented routes:

- `GET /api/v2/portfolio-risk/active-strategies`
- `GET /api/v2/portfolio-risk/var`
- `GET /api/v2/portfolio-risk/correlation`
- `GET /api/v2/portfolio-risk/concentration`
- `GET /api/v2/portfolio-risk/limits`
- `PUT /api/v2/portfolio-risk/limits`
- `GET /api/v2/portfolio-risk/limits/breaches`
- `GET /api/v2/portfolio-risk/alerts`
- `POST /api/v2/portfolio-risk/alerts/{alert_id}/ack`

## 12. Research Journal Completed

`services/journal_service.py` implements:

- durable entries
- title validation
- content updates
- tags
- tag counts
- text search
- deletion

Implemented routes:

- `GET /api/v2/journal`
- `POST /api/v2/journal`
- `PUT /api/v2/journal/{entry_id}`
- `DELETE /api/v2/journal/{entry_id}`
- `GET /api/v2/journal/tags`

## 13. Verification Performed

The verification suite is:

```text
backend/tests/test_studio_v2_contract.py
```

The final combined test command covered Studio V2 plus the recently remediated factor, principal component analysis, and screener math suites:

```bash
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_studio_v2_contract.py \
  backend/tests/test_factors_v2_math.py \
  backend/tests/test_pca_v2_remediation.py \
  backend/tests/test_screener_v2_math.py
```

Result:

```text
26 passed
```

The Studio V2 suite verifies:

- every route documented in `STUDIO_V2_API_ROUTES.md` is registered
- all seven templates exist and compile
- standalone exports are valid ZIP archives containing compilable Python
- Brinson effects reconcile to portfolio active return
- FIFO tax-lot calculations and holding-period classifications
- weighted composite-factor calculations
- Pareto dominance
- purged and embargoed cross-validation separation
- historical value at risk and conditional value at risk ordering
- component-risk reconciliation to total portfolio volatility
- cross-source price-return consistency
- public route smoke behavior
- isolated kernel execution
- real operating-system process cancellation

Additional checks performed:

- `python3 -m compileall -q backend/app/studio_v2`
- main application import
- OpenAPI schema generation
- exact Markdown route-contract comparison
- missing documented-file audit
- Git whitespace validation for the new Studio V2 files

The main application imported successfully, and the Studio V2 paths appeared in the generated OpenAPI document.

## 14. Work Remaining

The documented backend build is complete. The items below are the recommended next phases, not missing fake stubs.

### 14.1 Frontend Implementation

Build the frontend against the real API rather than duplicating calculations in React.

Recommended order:

1. Create a typed Studio V2 API client.
2. Generate or hand-maintain TypeScript response types from FastAPI OpenAPI.
3. Connect Algorithm Lab templates, snippets, composition, export, collaboration, and compute status.
4. Connect Backtest Studio run progress, results, comparison, attribution, slippage, tax, and scenarios.
5. Connect Robustness Lab.
6. Connect Factor Sandbox and governance.
7. Connect Optimizer views.
8. Connect Data Studio.
9. Build the Portfolio Risk page.
10. Connect the global research journal.

Every page should include loading, empty, partial-data, validation-error, and failed-request states.

### 14.2 Request Schemas and Generated Client

The current handlers deliberately accept flexible dictionaries because strategy and research payloads vary. Before exposing Studio V2 to third-party clients:

- add Pydantic request and response models
- document examples on every route
- add units to numeric fields
- distinguish percentages, decimals, currency, shares, and basis points
- generate a TypeScript client from OpenAPI
- enforce maximum request sizes

This is the highest-value backend hardening step after the frontend is functional.

### 14.3 Authentication and Authorization

Connect platform identity to:

- strategy ownership
- snippet ownership
- journal ownership
- collaboration-session owners
- invite issuance
- factor approvals
- risk-limit modification
- alert acknowledgement

The collaboration layer enforces invite roles, but the router still needs the application’s authenticated user injected into owner and actor fields.

### 14.4 Production Storage

SQLite is appropriate for local development and a single backend process. For horizontal production scaling:

- migrate document records to PostgreSQL
- move collaboration presence and transient job status to Redis
- move result arrays to object storage or Parquet
- retain metadata and object references in PostgreSQL
- add database migrations
- add backup and retention policies

Do not share one SQLite file across multiple containers.

### 14.5 Job Queue and Distributed Compute

The current compute guardrail is real and cancellable on one backend host. For distributed execution:

- introduce a worker queue
- store job state outside process memory
- route termination to the owning worker
- add CPU and memory limits
- add per-user quotas
- add wall-clock deadlines
- add worker-heartbeat detection
- preserve kernel checkpoints before worker eviction

Possible implementations include Celery, Dramatiq, Arq, or a dedicated Kubernetes job controller. Select one only when multi-host execution is actually required.

### 14.6 Market and Reference Data Connectors

Some services depend on data the existing local dataset may not contain:

- historical bid and ask quotes
- corporate event feeds
- point-in-time sector classifications
- factor return series
- borrow rates
- multi-asset contract metadata
- tax jurisdiction rules

The backend reports unavailable inputs or explicitly labels proxies. The next data pass should connect licensed or approved providers without changing the public API.

### 14.7 Attribution Data Preparation

Brinson attribution requires point-in-time:

- portfolio weights
- benchmark weights
- portfolio returns by sector
- benchmark returns by sector

Add these fields to backtest configuration and result persistence when sector classification data is available. Never substitute current sector classifications for historical point-in-time classifications without labeling the resulting bias.

### 14.8 Tax Jurisdictions

The current tax engine supports configurable short-term and long-term rates plus common wash-sale logic. Before using it for legal or client tax reporting:

- add jurisdiction-specific holding-period rules
- add tax calendars
- add dividend classifications
- add option and futures treatment
- add qualified-account exemptions
- add tax-loss carryforwards
- have the rules reviewed by a qualified tax professional

Keep the current output labeled as research simulation, not tax advice.

### 14.9 Observability

Add:

- structured request logs
- route latency histograms
- backtest and optimizer duration metrics
- job termination counters
- database-operation metrics
- WebSocket connection counts
- data-freshness alerts
- exception tracking
- audit-log retention

Do not log strategy source, invite tokens, secrets, or personally identifiable information.

### 14.10 Load and Failure Testing

Before production release, test:

- concurrent kernel sessions
- concurrent WebSocket collaborators
- process termination during large NumPy and pandas operations
- worker crashes
- SQLite lock contention in local mode
- very large backtest results
- partial market-data availability
- malformed strategy code
- invalid custom allocator code
- stale and expired collaboration tokens
- optimizer cancellation
- database restart and recovery

### 14.11 Security Review

The isolated execution worker makes jobs cancellable, but arbitrary Python remains a powerful capability. Before offering it to untrusted users:

- run workers in containers or microvirtual machines
- disable outbound network access by default
- mount read-only datasets
- apply CPU, memory, process, and file limits
- use short-lived work directories
- block host environment variables and credentials
- scan exported archives
- rotate `STUDIO_V2_AUDIT_KEY`

Operating-system process isolation alone is not a complete hostile-code sandbox.

## 15. Frontend Integration Map

| Frontend area | Backend routes |
|---|---|
| Template gallery | `/algorithm-lab/templates*` |
| Strategy composer | `/algorithm-lab/compose*` |
| Production export | `/algorithm-lab/export/{strategy_id}` |
| Collaboration | `/algorithm-lab/session/{session_id}/collaborate`, invite, participants |
| Compute panel | compute-status, kill, kill-all |
| Snippet drawer | `/algorithm-lab/snippets*` |
| Backtest runner | `/backtest/run`, result, metrics |
| Portfolio backtest | `/backtest/portfolio-run`, portfolio-result |
| Attribution | `/backtest/attribution/{run_id}` |
| Slippage | `/backtest/slippage-audit/{run_id}` |
| Tax | `/backtest/tax-report/{run_id}` |
| Scenarios | `/backtest/scenarios*` |
| Comparison | `/backtest/compare` |
| Robustness | `/robustness/run-core-tests`, audit-trail, adversarial |
| Factor builder | `/factors/evaluate`, ic-diagnostics |
| Factor governance | `/factors/library/{id}/*` |
| Optimizer | bayesian-search, ensemble, cross-validate |
| Data Studio | asset-classes, events, synthetic-ranges |
| Portfolio Risk | `/portfolio-risk/*` |
| Research journal | `/journal*` |

All paths in this table are relative to `/api/v2`.

## 16. Recommended Immediate Next Sprint

### Phase 1: Typed API Foundation

- Generate TypeScript types from OpenAPI.
- Create one API client with consistent error handling and cancellation.
- Add WebSocket reconnection and collaboration state handling.
- Add a frontend query-cache strategy.

### Phase 2: Algorithm Lab

- Build the template gallery.
- Add fork-to-editor navigation.
- Build the snippet drawer.
- Add compute status and process-kill controls.
- Add collaborator presence and cursor display.
- Add composition construction and execution.
- Add production ZIP download.

### Phase 3: Backtest and Robustness

- Build backtest progress and result tabs.
- Add portfolio backtesting.
- Add comparison tables and synchronized charts.
- Add attribution, slippage, tax, and scenario panels.
- Add robustness test configuration and persisted-result views.

### Phase 4: Factors, Optimizer, and Data

- Build composite factor controls.
- Add turnover-versus-decay charts.
- Add governance history and approval actions.
- Add Pareto, ensemble, and cross-validation views.
- Add asset-class, event, and synthetic-range overlays.

### Phase 5: Portfolio Risk

- Build active strategy selection.
- Add VaR and conditional VaR cards.
- Add correlation and component-risk visualizations.
- Add limit editing, breach display, and alert acknowledgement.

### Phase 6: Release Hardening

- Add Pydantic schemas.
- Add authenticated ownership and permissions.
- Configure production storage.
- Add integration, browser, load, and security tests.
- Configure monitoring and alerting.

## 17. Rules for the Next Developer

1. Do not replace these services with frontend-only mock data.
2. Do not recalculate financial metrics independently in the frontend.
3. Do not silently generate synthetic market, quote, event, sector, or factor data.
4. Preserve proxy labels when observed data is unavailable.
5. Add new behavior behind explicit request and response fields.
6. Add quantitative-invariant tests for every new formula.
7. Keep `/api/v2` backward compatible once the frontend begins consuming it.
8. Keep long-running computation outside the FastAPI event-loop process.
9. Preserve existing user changes in the repository.
10. Update both this handoff and `STUDIO_V2_API_ROUTES.md` when the public contract changes.

## 18. Definition of Done for the Next Phase

The frontend phase is complete when:

- every implemented API has a real consuming interface or is explicitly marked backend-only
- no production view depends on fixture or random data
- all loading and failure states are handled
- WebSocket collaboration reconnects safely
- long-running jobs can be monitored and terminated from the interface
- charts use backend-calculated metrics
- attribution and risk views disclose unavailable inputs
- TypeScript compilation, frontend tests, backend tests, and end-to-end browser tests pass
- the application can complete a full workflow:
  template fork → edit → execute → backtest → robustness → compare → approve → activate → monitor risk

