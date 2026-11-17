# Studio v3: Engineering, Quantitative Correctness and Release Standards

**Scope:** Quant Lens Studio v3  
**Purpose:** Mandatory review checklist for all implementation changes, refactors, bug fixes and releases.  
**Status:** Normative engineering standard  
**Related documents:** `docs/studio/plan/PLAN.md`, `CHECKLIST.md`, `DECISIONS.md`, `PAGES.md`, `REVIEW.md`

## 0. Enforcement and release policy

Every applicable requirement must be verified before a change is declared complete.

Each checklist item has one of four statuses:

- **PASS:** Verified with appropriate evidence.
- **FAIL:** Requirement violated.
- **N/A:** Requirement genuinely does not apply, with an explanation.
- **UNVERIFIED:** No sufficient evidence exists.

An unverified requirement must never be reported as passing.

### Severity classes

**P0: Release blocker**

- Look-ahead leakage or incorrect execution chronology.
- Incorrect financial calculations capable of materially misleading users.
- Unauthorized access, arbitrary code execution or data exposure.
- Hold-out leakage or unauthorized certification.
- Fabricated, stale or synthetic results represented as current observations.
- Silent corruption of persisted strategies, runs or financial records.

**P1: Must fix before affected functionality ships**

- Incorrect statistical methodology.
- Unreliable API or storage behavior.
- Missing critical error handling.
- Broken reproducibility.
- Material accessibility failures.
- Material performance regressions.
- Incorrect or misleading visualizations.

**P2: Quality requirement**

- Maintainability, duplication and documentation.
- Minor usability issues.
- Noncritical performance improvements.
- Design inconsistencies.

A documented decision may justify an intentional product limitation. It cannot waive a P0 defect.

### Change-specific verification

Every change must identify:

- [ ] Files and modules affected.
- [ ] User-visible behavior affected.
- [ ] Financial or statistical assumptions affected.
- [ ] Security boundaries affected.
- [ ] Existing tests that should detect regressions.
- [ ] New tests required.
- [ ] Applicable release gates.
- [ ] Known limitations and remaining risks.

Do not run an entire expensive validation suite after every trivial edit. Run focused checks during development and the complete required gates before release.

---

## 1. Automated quality gates

### Backend

```bash
cd backend

.venv/bin/ruff check \
  app/services/studio_v3 \
  app/api/studio_v3.py \
  tests/test_studio_v3_*.py

.venv/bin/ruff format --check \
  app/services/studio_v3 \
  app/api/studio_v3.py \
  tests/test_studio_v3_*.py

PYTHONPATH=. .venv/bin/python -m pytest \
  -q tests/test_studio_v3_*.py
```

- [ ] Ruff lint passes.
- [ ] Ruff formatting passes.
- [ ] All Studio unit tests pass.
- [ ] Relevant shared-engine tests pass.
- [ ] No unexpected warnings are suppressed.
- [ ] Tests execute under the documented Python version.
- [ ] Dependency installation is reproducible from the lockfile.

### Frontend

```bash
cd frontend

npx tsc --noEmit -p .
npx oxlint src/modules/studio
```

- [ ] TypeScript type checking passes.
- [ ] Oxlint passes.
- [ ] Relevant Vitest tests pass.
- [ ] Production build passes.
- [ ] Relevant Playwright tests pass.
- [ ] No hydration errors or unexpected browser-console errors.
- [ ] No broken API requests.
- [ ] No newly introduced accessibility violations.

### Security and supply chain

```bash
gitleaks git --redact .
```

- [ ] Secret scanning passes.
- [ ] Dependency vulnerability scanning passes.
- [ ] New dependencies have acceptable licenses.
- [ ] No unauthorized external services or telemetry are introduced.
- [ ] Production secrets are absent from browser bundles.

### Verification integrity

- [ ] Commands actually executed are recorded.
- [ ] Exit codes are preserved.
- [ ] Failures are never hidden by shell pipelines or ignored return codes.
- [ ] Test skips and expected failures are reviewed.
- [ ] A failed gate cannot be converted to PASS by changing its reporting.
- [ ] CI runs on a clean checkout.
- [ ] Local and CI environments use compatible dependency versions.
- [ ] No `--no-verify` bypass is used without documented approval.

**Important:** These commands establish the baseline. Additional tests must be added when a change affects numerical algorithms, authentication, storage, concurrency or production deployment.

---

## 2. Quantitative research integrity

### 2.1 Point-in-time correctness

- [ ] Every signal uses only information available at its decision timestamp.
- [ ] Every feature has an explicit observation timestamp.
- [ ] Data availability is distinguished from data observation.
- [ ] Corporate announcements and financial statements respect publication dates.
- [ ] Fundamentals respect realistic filing and ingestion delays.
- [ ] Revised macroeconomic data is not treated as originally published data.
- [ ] Universe membership is evaluated point-in-time wherever historical membership data exists.
- [ ] Rolling indicators do not use future observations.
- [ ] Centered rolling windows are prohibited for predictive features.
- [ ] Cross-sectional normalization uses only the eligible universe at that timestamp.
- [ ] Missing historical availability metadata produces a limitation or refusal.
- [ ] Any intentional retrospective analysis is explicitly labeled non-predictive.

### 2.2 Execution chronology

- [ ] Signals and fills have separate timestamps.
- [ ] Default close-of-bar signals execute no earlier than the next eligible open.
- [ ] Same-close execution is permitted only when the information and order-submission chronology support it.
- [ ] Completed closing prices are not assumed known before the close.
- [ ] Higher-timeframe indicators use the last completed higher-timeframe bar.
- [ ] Market holidays and missing sessions do not create fictional execution opportunities.
- [ ] Orders are not executed on suspended or unavailable securities.
- [ ] A future-peeking strategy fails an explicit adversarial test.
- [ ] Truncating future data does not change earlier signals.

### 2.3 Parameter selection

- [ ] Optimization uses an explicitly defined training period.
- [ ] Model selection and final evaluation are separated.
- [ ] Every reported out-of-sample result is genuinely out-of-sample relative to selection.
- [ ] Walk-forward parameters are selected using only preceding training data.
- [ ] Rolling covariance and portfolio weights are lagged correctly.
- [ ] Regime definitions do not depend on future observations.
- [ ] Feature selection is repeated inside the training fold.
- [ ] Hyperparameter tuning does not use the final hold-out.
- [ ] Post-hoc changes to strategy logic invalidate earlier independent validation claims.
- [ ] In-sample results are labeled in-sample wherever displayed.

### 2.4 Multiple testing and selection bias

- [ ] Every evaluated strategy candidate has a persistent trial identifier.
- [ ] Parameter sweeps record attempted, completed, failed and excluded candidates.
- [ ] Trial lineage connects variants to their parent strategy.
- [ ] The ledger records selection criteria and optimization objectives.
- [ ] Effective trial-count methodology is documented.
- [ ] Deflated Sharpe uses the intended trial-count and return-distribution assumptions.
- [ ] PBO is computed only when its sampling and candidate requirements are satisfied.
- [ ] CSCV partitions preserve the documented methodology.
- [ ] Purging and embargo account for overlapping information intervals.
- [ ] Repeated hold-out inspection is logged and surfaced as a limitation.
- [ ] Statistical corrections are not presented as guarantees of future profitability.

### 2.5 Statistical inference

- [ ] Sharpe, Sortino, Calmar, drawdown and volatility definitions are canonical.
- [ ] Sample versus population variance conventions are explicit.
- [ ] Annualization reflects the sampling frequency and return convention.
- [ ] Serial correlation is considered when estimating uncertainty.
- [ ] Confidence intervals use a method appropriate to the dependence structure.
- [ ] Bootstrap resampling preserves dependence where necessary.
- [ ] Small-sample inference is refused or qualified.
- [ ] P-values and confidence intervals are not interpreted as probabilities that a strategy is profitable.
- [ ] Multiple comparisons are accounted for where applicable.
- [ ] Nonstationarity and regime instability are disclosed.
- [ ] No metric is reported with precision unsupported by its data.

---

## 3. Backtesting engine correctness

### 3.1 Shared execution contract

- [ ] Vector and event engines implement the same documented execution semantics.
- [ ] Entry and exit priority is deterministic.
- [ ] Same-bar entry and exit behavior is explicitly specified.
- [ ] Long and short accounting are consistent.
- [ ] Cash and equity reconcile after every bar.
- [ ] Positions reconcile with the trade ledger.
- [ ] Every trade has a valid entry and exit chronology.
- [ ] No negative or nonfinite position quantity is silently accepted.
- [ ] Fractional-share rules are explicit.
- [ ] Leverage and exposure limits are enforced before execution.
- [ ] Position limits remain valid after partial fills.
- [ ] The system never silently creates capital.

### 3.2 Fill modeling

- [ ] Market, stop and target fills use the correct bar information.
- [ ] Stop gaps fill at the open when the modeled market is executable there.
- [ ] Simultaneous stop/target ambiguity uses a documented conservative policy.
- [ ] The policy is described as an assumption, not historical truth.
- [ ] Slippage is applied in the economically adverse direction.
- [ ] Commission is charged on both entry and exit.
- [ ] Minimum commissions are correctly applied.
- [ ] Volume participation limits use executable-bar volume.
- [ ] Partial fills preserve remaining quantities and order state.
- [ ] Unfilled orders are reported.
- [ ] Borrow fees apply only to the appropriate short exposure.
- [ ] Borrow availability and locate constraints are modeled or disclosed as missing.
- [ ] Dividend obligations on shorts are modeled when data permits.
- [ ] Delisting and suspension assumptions are disclosed.
- [ ] Intrabar ordering is not inferred from daily OHLC alone.

### 3.3 Accounting invariants

- [ ] Cash changes equal signed trade cash flows minus fees.
- [ ] Equity equals cash plus marked position value under the documented accounting convention.
- [ ] Realized and unrealized P&L reconcile with equity changes.
- [ ] Entry costs are allocated consistently across partial exits.
- [ ] Fees and slippage are not double-counted.
- [ ] Borrow charges are not omitted from net returns.
- [ ] Gross and net returns reconcile with reported costs.
- [ ] Position quantities return to zero after complete liquidation.
- [ ] A zero-cost, zero-return strategy preserves initial capital.
- [ ] A no-trade strategy has a flat equity curve.
- [ ] All accounting invariants are checked within documented numerical tolerances.

### 3.4 Independent numerical verification

- [ ] Vector and event engines match on identical fixtures.
- [ ] An independent reference implementation or hand-calculated fixture validates both engines.
- [ ] Tests cover longs, shorts, gaps, stops, targets, scaling and delistings.
- [ ] Tests include adversarial OHLC sequences.
- [ ] Tests include sparse and missing market data.
- [ ] Tests include zero-volume sessions.
- [ ] Tests include extreme prices and position sizes.
- [ ] Floating-point tolerances are explicit and justified.
- [ ] Golden fixtures are reviewed before expected values change.
- [ ] No test derives its expected result solely from the implementation being tested.

---

## 4. Data integrity and market-data provenance

### 4.1 Data contracts

- [ ] Every dataset has a documented schema.
- [ ] Required columns and data types are validated.
- [ ] Timestamps have explicit timezone semantics.
- [ ] Symbols use stable identifiers where available.
- [ ] Duplicate keys are detected.
- [ ] OHLC consistency is checked.
- [ ] Negative prices and volumes are rejected unless the instrument permits them.
- [ ] Missing observations are distinguished from genuine zero values.
- [ ] Corporate actions are handled consistently.
- [ ] Adjustment conventions are consistent within each return calculation.
- [ ] Mixed adjusted/raw data cannot silently enter a total-return calculation.

### 4.2 Provenance

- [ ] Every run records its dataset version.
- [ ] Source provider and retrieval date are recorded.
- [ ] Data transformations are reproducible.
- [ ] Adjustment methodology is recorded.
- [ ] Coverage dates are recorded.
- [ ] Universe construction methodology is recorded.
- [ ] Survivorship limitations are recorded.
- [ ] Missing delisted securities are disclosed.
- [ ] Data quality failures are visible to downstream consumers.

### 4.3 Freshness and Live

- [ ] Last available observation is displayed.
- [ ] Freshness thresholds depend on market and data frequency.
- [ ] Non-trading days are handled correctly.
- [ ] Historical signals are never presented as current signals.
- [ ] Actionable Live outputs are disabled when data exceeds the permitted freshness threshold.
- [ ] Paper-trading timestamps correspond to actual forward observations.
- [ ] Alerts do not silently fire from stale observations.
- [ ] Failed refresh jobs are surfaced.
- [ ] Partial refreshes do not create inconsistent datasets.
- [ ] Dataset replacement is atomic or recoverable.

### 4.4 Data refresh migration

- [ ] Original datasets are backed up.
- [ ] Schema migrations are versioned.
- [ ] Historical coverage is compared before and after.
- [ ] Symbol losses are explained.
- [ ] Corporate-action spot checks pass.
- [ ] Price and return discontinuities are investigated.
- [ ] A rollback procedure exists.
- [ ] Existing saved runs retain their original data-version references.

---

## 5. Validation, optimization and certification

### 5.1 Optimization

- [ ] Search spaces are explicit.
- [ ] Parameter constraints are enforced before evaluation.
- [ ] Invalid parameter combinations are counted and reported.
- [ ] Optimization objectives use canonical metric definitions.
- [ ] Random searches use reproducible seeds.
- [ ] Optuna or equivalent optimizer versions are recorded.
- [ ] Results distinguish evaluated cells from unexplored space.
- [ ] Plateau detection uses a documented neighborhood definition.
- [ ] Parameter stability is not inferred from a single optimum.
- [ ] Pareto comparisons use consistent objectives.
- [ ] Optimization failures cannot silently bias reported rankings.

### 5.2 Walk-forward

- [ ] Training and evaluation windows are explicitly indexed.
- [ ] Purge and embargo intervals are validated.
- [ ] Training does not contain evaluation labels.
- [ ] Each evaluation window uses the parameters selected before that window.
- [ ] Stitched out-of-sample returns preserve chronological order.
- [ ] Window boundaries do not duplicate observations.
- [ ] Performance is calculated from the actual stitched equity path.
- [ ] Missing or insufficient windows produce a skipped result.
- [ ] Anchored and rolling methods are independently tested.
- [ ] Walk-forward efficiency uses documented definitions.

### 5.3 Robustness testing

- [ ] Every test evaluates the actual user strategy.
- [ ] Noise tests use documented distributions.
- [ ] Permutation tests state their null hypothesis.
- [ ] Random-entry baselines preserve appropriate exposure and trading constraints.
- [ ] Delay tests preserve the correct execution chronology.
- [ ] Cost shocks affect the same accounting model as normal execution.
- [ ] Parameter perturbations remain within valid domains.
- [ ] Synthetic shocks are labeled synthetic.
- [ ] Monte Carlo uncertainty is not presented as a guaranteed future range.
- [ ] Every skipped test reports its reason.

### 5.4 Hold-out isolation

- [ ] Hold-out membership is established before tuning.
- [ ] Hold-out observations are excluded from development summaries that would leak performance information.
- [ ] Access controls are enforced server-side.
- [ ] Hold-out access is authenticated.
- [ ] Agent access budgets are enforced atomically.
- [ ] Concurrent requests cannot bypass budgets.
- [ ] Every exposure is recorded in an append-only audit trail.
- [ ] Repeated exposure changes the reported independence status.
- [ ] Failed authorization does not reveal protected statistics.
- [ ] Certification does not implicitly reopen the hold-out.

### 5.5 Verdict and certification

- [ ] Verdict inputs are server-computed.
- [ ] Verdict weights and thresholds are versioned.
- [ ] Missing tests cannot silently count as passes.
- [ ] Grade caps are enforced.
- [ ] The verdict reports its strongest limiting reason.
- [ ] Statistical uncertainty is distinguished from product scoring.
- [ ] The certificate identifies the exact strategy version.
- [ ] The certificate identifies data and execution settings.
- [ ] The certificate identifies validation-method versions.
- [ ] Certification recomputes or verifies trusted persisted results.
- [ ] Client-supplied metrics cannot be certified.
- [ ] A certificate hash changes when materially relevant inputs change.
- [ ] Certification failures are explicit.
- [ ] A certificate is never described as proof of future profitability.

---

## 6. Strategy compilation and language safety

### 6.1 One strategy specification

- [ ] Blocks, formula and Python modes share a canonical strategy contract.
- [ ] Equivalent supported strategies produce equivalent signals.
- [ ] Equivalent signals produce equivalent trades under the same execution settings.
- [ ] Unsupported conversions are rejected rather than silently approximated.
- [ ] Parameter types and ranges are validated.
- [ ] Missing required parameters are rejected.
- [ ] Unused parameters are reported.
- [ ] Strategy specifications are versioned.
- [ ] Older saved specifications remain readable or have explicit migrations.

### 6.2 Formula evaluation

- [ ] Formula syntax is parsed into a constrained AST.
- [ ] Allowed operations are explicitly enumerated.
- [ ] Unknown functions are rejected.
- [ ] Attribute access and dynamic imports are prohibited unless explicitly required and proven safe.
- [ ] Arbitrary `eval` and `exec` are prohibited.
- [ ] Formula complexity has a bounded budget.
- [ ] Invalid numeric operations produce structured errors.
- [ ] Indicator warm-up periods are respected.
- [ ] Look-ahead operations are rejected.
- [ ] Compiler errors identify the offending location.
- [ ] Formula evaluation is deterministic.

### 6.3 Python strategy execution

- [ ] Untrusted Python is never executed in the main API process.
- [ ] A child process is not assumed to provide a complete security boundary.
- [ ] Untrusted execution uses an appropriately isolated environment before public exposure.
- [ ] Filesystem access is restricted.
- [ ] Network access is restricted.
- [ ] Process creation is restricted.
- [ ] Environment variables and secrets are inaccessible.
- [ ] CPU, memory, runtime and output budgets are enforced.
- [ ] Process termination is reliable.
- [ ] Host resources remain protected after abnormal termination.
- [ ] Strategy errors cannot crash the API server.
- [ ] Sandbox escape attempts have negative security tests.
- [ ] Python execution is disabled for untrusted users if adequate isolation is unavailable.

---

## 7. Application and API security

### 7.1 Authentication and authorization

- [ ] Every protected operation requires authenticated identity.
- [ ] Client-provided actor labels are not treated as proof of identity.
- [ ] Human-only operations are enforced through trusted authorization.
- [ ] Agent tokens have explicit scopes.
- [ ] Agent tokens can be revoked.
- [ ] User ownership is checked on every strategy, run and artifact.
- [ ] Cross-user access is tested.
- [ ] Authentication failures reveal no protected data.
- [ ] Administrative operations require separate authorization.
- [ ] Security decisions are logged without exposing secrets.

### 7.2 API boundaries

- [ ] Requests use validated schemas.
- [ ] Unknown fields are rejected where appropriate.
- [ ] Numeric bounds and array sizes are enforced.
- [ ] Input payload sizes are bounded.
- [ ] Response schemas are stable.
- [ ] Error responses are structured.
- [ ] Internal stack traces are not exposed to clients.
- [ ] Rate limits apply to expensive endpoints.
- [ ] Resource quotas are enforced per authenticated principal.
- [ ] Cancellation and retry behavior are defined.
- [ ] CORS and CSRF controls match the authentication model.
- [ ] Sensitive actions are protected against replay where necessary.

### 7.3 Storage and secrets

- [ ] SQL uses parameterized queries.
- [ ] User-supplied paths cannot escape designated storage roots.
- [ ] File permissions follow least privilege.
- [ ] Secrets are excluded from logs and exceptions.
- [ ] Sensitive tokens are not embedded in URLs.
- [ ] Temporary files have controlled lifetimes.
- [ ] Uploaded files have size and format limits.
- [ ] Stored artifacts are associated with their owner.
- [ ] Data deletion respects retention policy.
- [ ] Backups and restoration procedures are tested.

### 7.4 AI and agent security

- [ ] Agent permissions are narrower than human permissions where required.
- [ ] Tool inputs are validated independently of the agent.
- [ ] External text is treated as untrusted.
- [ ] Prompt injection cannot authorize privileged actions.
- [ ] Agent calls are attributable to a verified principal.
- [ ] Agent spending and compute budgets are enforced.
- [ ] Tool failures do not silently trigger repeated expensive execution.
- [ ] Human approval is required for designated sensitive actions.
- [ ] Agent output cannot directly overwrite trusted numerical results.
- [ ] Audit logs distinguish human actions from automated actions.

---

## 8. Backend engineering

### 8.1 Architecture

- [ ] Each module has a clearly defined responsibility.
- [ ] Shared financial behavior has one canonical implementation.
- [ ] Domain logic is separated from HTTP handling.
- [ ] Persistence logic is separated from numerical algorithms.
- [ ] UI formatting does not determine backend financial results.
- [ ] Circular dependencies are avoided.
- [ ] Public interfaces are documented.
- [ ] Refactors preserve observable behavior unless intentionally changed.
- [ ] Existing callers are identified before shared interfaces change.
- [ ] New abstractions solve demonstrated duplication or complexity.

### 8.2 Python quality

- [ ] Public functions have meaningful type annotations.
- [ ] Return types represent possible failures accurately.
- [ ] Exceptions are specific.
- [ ] Broad exception handling is justified.
- [ ] No silent fallback changes financial meaning.
- [ ] No unnecessary mutable global state.
- [ ] Resource cleanup is deterministic.
- [ ] Numeric conversions are explicit.
- [ ] Integer and floating-point boundaries are checked.
- [ ] Named constants replace repeated unexplained literals.
- [ ] Comments explain invariants, assumptions and unusual decisions.
- [ ] Dead code and stale compatibility paths are removed only after usage checks.

### 8.3 Concurrency and job execution

- [ ] Job IDs are unique.
- [ ] Job ownership is verified.
- [ ] Job state transitions are valid.
- [ ] Cancellation is idempotent.
- [ ] Retried requests do not duplicate financial or irreversible actions.
- [ ] Progress updates are monotonic or explicitly reset.
- [ ] Concurrent writes cannot corrupt storage.
- [ ] Worker crashes leave recoverable job states.
- [ ] Long-running work does not block the API event loop.
- [ ] Queue capacity and concurrency are bounded.
- [ ] Resource exhaustion is handled predictably.
- [ ] Results are committed atomically.
- [ ] Orphaned jobs and artifacts are recoverable or cleaned safely.

---

## 9. Frontend engineering

### 9.1 React and TypeScript

- [ ] API responses have explicit types.
- [ ] Runtime validation exists where untrusted API data enters the UI.
- [ ] No unjustified `any` or unsafe type assertions.
- [ ] Server state and local UI state are distinguished.
- [ ] Effects do not create unnecessary request loops.
- [ ] Async requests handle cancellation and stale responses.
- [ ] Loading states are accurate.
- [ ] Errors are visible and actionable.
- [ ] Components do not duplicate business logic.
- [ ] Large views are decomposed by responsibility.
- [ ] Expensive visualizations avoid unnecessary rerenders.
- [ ] All interactive controls have real behavior.

### 9.2 Data presentation

- [ ] Every financial number comes from a verified result or documented transformation.
- [ ] Percent, basis points, currency and raw ratios are distinguished.
- [ ] Decimal precision is consistent.
- [ ] Missing values are not silently rendered as zero.
- [ ] Negative values use consistent formatting.
- [ ] Time ranges are explicit.
- [ ] Benchmark comparisons use compatible return definitions.
- [ ] Statistical uncertainty is displayed where material.
- [ ] Tooltips do not contradict primary labels.
- [ ] Data limitations are accessible near the affected output.

### 9.3 UX and visual design

- [ ] Every page has a clear primary task.
- [ ] Every chart answers a specific question.
- [ ] The selected chart type matches the data.
- [ ] Repeated metrics and redundant captions are removed.
- [ ] Visual hierarchy follows analytical importance.
- [ ] Color conveys meaning rather than decoration.
- [ ] Status colors are consistent.
- [ ] Default charts are useful without customization.
- [ ] Customization controls do not obscure the analysis.
- [ ] Empty states explain what is missing.
- [ ] Skipped states explain why.
- [ ] Error states explain the next action.
- [ ] Destructive actions have appropriate confirmation.
- [ ] Saved settings behave consistently across pages.

### 9.4 Chart correctness

- [ ] Chart timestamps match the backend dataset.
- [ ] Chart prices match the backtesting data source.
- [ ] Indicators use the same definitions as the strategy engine.
- [ ] Indicator warm-up differences are documented and tested.
- [ ] Trade markers align with actual fill timestamps.
- [ ] Entry and exit prices match the trade ledger.
- [ ] Corporate-action adjustments are consistent.
- [ ] Logarithmic scales reject nonpositive values appropriately.
- [ ] Percentage and indexed scales have correct baselines.
- [ ] Downsampling preserves important extrema where necessary.
- [ ] Downsampling does not silently alter analytical conclusions.
- [ ] Replay cannot reveal future bars.
- [ ] Saved drawings retain correct time and price coordinates.
- [ ] Exported figures preserve units, legends and data provenance.

### 9.5 Responsive behavior

- [ ] Layout works at 390 px.
- [ ] Layout works at 768 px.
- [ ] Layout works at 1024 px.
- [ ] Layout works at 1440 px.
- [ ] Tables use intentional overflow behavior.
- [ ] Essential controls remain reachable on mobile.
- [ ] Charts remain readable on smaller screens.
- [ ] Dialogs do not overflow the viewport.
- [ ] Keyboard focus remains visible.
- [ ] Touch targets are usable.

---

## 10. Accessibility

- [ ] Inputs have accessible labels.
- [ ] Icon-only buttons have accessible names.
- [ ] Form errors are associated with their controls.
- [ ] Keyboard navigation follows a logical order.
- [ ] All essential functionality is keyboard accessible.
- [ ] Focus indicators are visible.
- [ ] Dialogs manage focus correctly.
- [ ] Escape closes appropriate overlays.
- [ ] Color is never the sole carrier of information.
- [ ] Contrast meets the selected WCAG target.
- [ ] Charts have accessible names and textual summaries.
- [ ] Tables have meaningful headers.
- [ ] Dynamic status updates are announced appropriately.
- [ ] Reduced-motion preferences are respected.
- [ ] Screen-reader testing covers critical workflows.
- [ ] Automated accessibility checks pass.

---

## 11. Performance and scalability

### 11.1 Numerical performance

- [ ] Hot paths are profiled before optimization.
- [ ] Vectorization or compilation is used where justified.
- [ ] Numba compilation time is distinguished from steady-state runtime.
- [ ] Benchmark datasets and hardware are recorded.
- [ ] Peak memory is measured.
- [ ] Performance comparisons use equivalent workloads.
- [ ] Optimization does not change numerical results beyond accepted tolerances.
- [ ] Caches use appropriate version keys.
- [ ] Cache invalidation is tested.
- [ ] Large allocations have explicit limits.

### 11.2 API performance

- [ ] Request latency budgets are defined per endpoint.
- [ ] Long jobs return a job identifier promptly.
- [ ] Polling does not create excessive server load.
- [ ] Concurrent request behavior is tested.
- [ ] Timeouts are explicit.
- [ ] Large responses are paginated or bounded.
- [ ] Serialization overhead is measured when material.
- [ ] Failed jobs release resources.
- [ ] Rate limits protect expensive computations.

### 11.3 Frontend performance

- [ ] Initial JavaScript bundle size is monitored.
- [ ] Heavy editors and chart libraries load on demand.
- [ ] Large tables use virtualization where beneficial.
- [ ] Charts avoid unnecessary full rerenders.
- [ ] Interaction latency is measured.
- [ ] Layout shifts are controlled.
- [ ] Memory usage remains stable during repeated navigation.
- [ ] Browser performance is tested with realistic data.
- [ ] Performance budgets are checked in CI where stable measurement is feasible.

### 11.4 Budget enforcement

The existing Studio performance targets remain the baseline, but each target must identify:

- Workload.
- Dataset.
- Hardware.
- Warm or cold cache.
- Number of repetitions.
- Measurement method.
- Acceptance threshold.

A performance claim without these details is unverified.

---

## 12. Reproducibility and deterministic computation

- [ ] Strategy specifications use canonical serialization.
- [ ] Serialization order is deterministic.
- [ ] Numerical normalization rules are explicit.
- [ ] Data version is included in provenance.
- [ ] Execution settings are included.
- [ ] Relevant software and algorithm versions are included.
- [ ] Random seeds are included.
- [ ] External nondeterministic dependencies are recorded.
- [ ] Repeated runs under the supported environment produce equivalent results.
- [ ] Hashes are computed from canonical representations.
- [ ] Hash changes are tested when relevant inputs change.
- [ ] Hash stability is tested when irrelevant metadata changes.
- [ ] Results are compared using exact equality or documented numerical tolerances as appropriate.
- [ ] Saved runs remain interpretable after software upgrades.
- [ ] Reproduction failures identify the mismatched component.

A cryptographic hash establishes identity of the serialized content. It does not independently establish that the underlying financial calculation is correct.

---

## 13. Testing methodology

### 13.1 Unit tests

- [ ] Every nontrivial branch has an appropriate test.
- [ ] Boundary conditions are tested.
- [ ] Failure paths are tested.
- [ ] Tests assert behavior rather than implementation details.
- [ ] Test names describe the invariant.
- [ ] Expected results are independently justified.
- [ ] Tests are deterministic.
- [ ] Tests avoid unnecessary external dependencies.

### 13.2 Property-based and metamorphic tests

Where applicable:

- [ ] Scaling initial capital preserves percentage returns under scale-invariant cost assumptions.
- [ ] Increasing nonnegative costs cannot improve an otherwise identical realized P&L path.
- [ ] Removing future bars does not change earlier signals.
- [ ] Identical inputs produce identical results.
- [ ] Reordering independent input symbols does not change aggregate results except where documented tie-breaking applies.
- [ ] No-trade strategies preserve capital.
- [ ] Zero-return assets produce expected accounting behavior.
- [ ] Portfolio weights satisfy declared constraints.
- [ ] Equity and cash accounting identities hold.
- [ ] Serialization round trips preserve strategy meaning.

Properties must state their assumptions. For example, scaling capital does not preserve percentage returns when fixed minimum commissions or liquidity constraints are active.

### 13.3 Integration tests

- [ ] API requests reach the correct numerical engine.
- [ ] Saved strategy versions reload correctly.
- [ ] Jobs transition through valid states.
- [ ] Cancellation works.
- [ ] Results persist correctly.
- [ ] Frontend and backend output contracts agree.
- [ ] Agent and browser interfaces return consistent trusted results.
- [ ] Authorization is enforced across interfaces.
- [ ] Data refresh invalidates affected caches.
- [ ] Existing saved runs survive supported migrations.

### 13.4 End-to-end tests

- [ ] User creates a strategy.
- [ ] User compiles and previews it.
- [ ] User saves a version.
- [ ] User runs a backtest.
- [ ] User inspects trades and charts.
- [ ] User optimizes parameters.
- [ ] User validates the selected strategy.
- [ ] User accesses the hold-out through the authorized flow.
- [ ] User exports or reproduces results.
- [ ] Failures are surfaced correctly.
- [ ] The complete workflow works with representative real data.

### 13.5 Regression policy

- [ ] Every fixed correctness bug gets a regression test.
- [ ] Every fixed security bug gets a negative test.
- [ ] Golden fixtures are not updated merely to make failing tests pass.
- [ ] Snapshot changes are reviewed visually.
- [ ] Flaky tests are investigated rather than permanently ignored.
- [ ] Test coverage is evaluated by risk, not percentage alone.
- [ ] Test execution time is monitored.

---

## 14. Dependencies, licenses and supply chain

- [ ] New dependencies solve a documented need.
- [ ] Existing dependencies are considered before adding another.
- [ ] Licenses are compatible with intended distribution.
- [ ] Transitive dependency risks are reviewed.
- [ ] Package versions are locked.
- [ ] Integrity checks are preserved.
- [ ] Abandoned packages are reviewed before adoption.
- [ ] Security advisories are monitored.
- [ ] Third-party notices are maintained.
- [ ] Copied code retains required attribution.
- [ ] Dependency removal includes import and build checks.
- [ ] Development-only packages do not unnecessarily enter production bundles.

---

## 15. Observability and operational reliability

- [ ] Requests have correlation identifiers.
- [ ] Jobs have traceable identifiers.
- [ ] Logs distinguish operational failures from user validation failures.
- [ ] Errors contain sufficient debugging context.
- [ ] Sensitive information is redacted.
- [ ] Numerical failures are observable.
- [ ] Data refresh failures are observable.
- [ ] Job duration and failure rates are measurable.
- [ ] Resource saturation is detectable.
- [ ] Alert delivery failures are recorded.
- [ ] Retries use bounded policies.
- [ ] Idempotency prevents duplicate actions.
- [ ] Recovery procedures are documented.
- [ ] Operational dashboards use real metrics.
- [ ] No monitoring metric is fabricated or silently replaced by a placeholder.

---

## 16. Documentation and architectural decisions

- [ ] Public behavior changes are documented.
- [ ] Statistical definitions are documented.
- [ ] Numerical assumptions are documented.
- [ ] Data limitations are documented.
- [ ] Security limitations are documented.
- [ ] Performance claims include measurements.
- [ ] Deprecated behavior is identified.
- [ ] Migration requirements are documented.
- [ ] Checklist completion reflects actual evidence.
- [ ] Decisions record rationale and alternatives.
- [ ] Temporary exceptions have an owner and expiration or review condition.
- [ ] Documentation does not claim untested functionality is verified.

A decision record must include:

1. Decision identifier and date.
2. Affected functionality.
3. Problem and evidence.
4. Alternatives considered.
5. Selected approach.
6. Trade-offs.
7. Security and correctness implications.
8. Tests required.
9. Conditions for revisiting the decision.

---

## 17. Git and change management

- [ ] The working tree is inspected before editing.
- [ ] Unrelated user changes remain untouched.
- [ ] Only intended files are staged.
- [ ] Diff is reviewed before committing.
- [ ] Generated artifacts are intentional.
- [ ] No secrets or credentials are committed.
- [ ] Commit message describes the behavior changed.
- [ ] Relevant tests pass before commit.
- [ ] Documentation and checklists are updated.
- [ ] The commit is pushed to the intended branch.
- [ ] The remote commit SHA is verified.
- [ ] The final report identifies the exact commit.
- [ ] No force push or history rewrite occurs without explicit authorization.
- [ ] `research_exports/` is preserved.

---

## 18. Studio-specific release blockers

The following conditions require special attention in the current Studio v3 implementation.

### 18.1 Market-data freshness

- [ ] Historical data is accurately labeled.
- [ ] Stale data cannot produce apparently current actionable signals.
- [ ] Live alerts are gated by data freshness.
- [ ] Forward performance uses genuinely subsequent observations.
- [ ] Adjustment inconsistencies are resolved or prominently disclosed.

### 18.2 Actor identity

- [ ] `X-Studio-Actor` is not trusted as authentication.
- [ ] Human and agent permissions are enforced by verified identity.
- [ ] Hold-out budgets cannot be bypassed by changing headers.
- [ ] Freeze and certification permissions are enforced server-side.

### 18.3 Python execution

- [ ] Current child-process restrictions are documented as defense-in-depth.
- [ ] Untrusted execution remains disabled until adequate isolation is verified.
- [ ] Sandbox tests cover filesystem, network, process and environment access.
- [ ] Resource exhaustion tests pass.

### 18.4 Chart and engine parity

- [ ] Chart indicators agree with strategy indicators.
- [ ] EMA initialization differences are resolved or explicitly represented.
- [ ] Chart trade markers use actual execution prices.
- [ ] Chart and backtest use compatible price adjustments.
- [ ] Replay reveals no future data.

### 18.5 Incomplete functionality

- [ ] Unimplemented controls are disabled or removed.
- [ ] Unimplemented API behavior is not advertised.
- [ ] Pending acceptance tests remain visibly pending.
- [ ] No incomplete phase is marked complete solely because its code exists.

---

## 19. Final release evidence

Every completed change must produce a concise verification report.

### Change summary

- Branch:
- Commit SHA:
- Files changed:
- Behavior changed:
- Root cause:
- Risk classification:

### Verification

| Gate | Result | Evidence |
|---|---|---|
| Ruff lint | PASS / FAIL / N/A | |
| Ruff format | PASS / FAIL / N/A | |
| Backend tests | PASS / FAIL / N/A | |
| TypeScript | PASS / FAIL / N/A | |
| Oxlint | PASS / FAIL / N/A | |
| Frontend tests | PASS / FAIL / N/A | |
| Browser E2E | PASS / FAIL / N/A | |
| Quant invariants | PASS / FAIL / N/A | |
| Security checks | PASS / FAIL / N/A | |
| Performance | PASS / FAIL / N/A | |
| Documentation | PASS / FAIL / N/A | |
| Remote verification | PASS / FAIL / N/A | |

### Final review

- [ ] The requested behavior works.
- [ ] No P0 issue remains.
- [ ] No applicable P1 issue remains for the affected release.
- [ ] Required tests passed.
- [ ] Results are numerically defensible.
- [ ] Security boundaries are respected.
- [ ] Data limitations are accurately disclosed.
- [ ] Browser behavior is verified where relevant.
- [ ] Documentation matches implementation.
- [ ] Remaining limitations are explicitly stated.
- [ ] Commit and remote state are verified.

**Completion rule:** A change is complete only when its applicable requirements have passed and the evidence is recorded. Implemented, tested, verified and production-ready are separate statuses.

---

## 20. Engineering principles

1. **Correctness before optimization.** Never accelerate an unverified numerical algorithm.
2. **Evidence before claims.** Every reported result must be reproducible or explicitly qualified.
3. **Time is part of the data model.** Observation, availability, decision and execution timestamps must remain distinct.
4. **Financial assumptions are executable contracts.** Costs, fills, corporate actions and portfolio constraints must be tested.
5. **Security is enforced at trusted boundaries.** Browser state and agent claims cannot grant privileges.
6. **One canonical implementation per financial concept.** Reuse verified shared behavior.
7. **Independent tests matter more than self-consistency.** Two engines agreeing does not prove either is correct.
8. **Uncertainty must remain visible.** Insufficient evidence produces a limitation, not a fabricated conclusion.
9. **Every feature must justify its complexity.** Remove controls and abstractions that do not improve the user's task.
10. **Release status follows verification.** A checked box is evidence of completed verification, never a substitute for it.

## References

- NIST SP 800-218, Secure Software Development Framework.
- OWASP Application Security Verification Standard 5.0.
- Bailey et al., *The Probability of Backtest Overfitting*, Journal of Computational Finance.
- Bailey and López de Prado, *The Deflated Sharpe Ratio*, Journal of Portfolio Management.
- Quant Lens Studio v3 plan, checklist and decisions.
