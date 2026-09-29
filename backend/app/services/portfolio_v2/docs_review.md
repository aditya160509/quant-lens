# Portfolio v2 — Cross-Document Audit & Consistency Review

**Generated:** 2026-07-10  
**Scope:** All markdown files under `backend/app/services/` plus root spec `portfolio features.md`

---

## 1. Cross-Document Consistency

### Feature Numbering Mismatch (Spec vs Implementation)

The root spec (`portfolio features.md`) defines features **FEATURE 1–15** with gaps: there is no FEATURE 11 or FEATURE 14. The feature list bottom of line 775–777 confirms "only 13 features." Portfolio v2's `README.md` normalizes its internal F01–F13 by skipping the spec's numbering gaps:

| Portfolio_v2 label | Spec heading | Notes |
|---|---|---|
| **F01** | FEATURE 1 — Portfolio Construction & Optimization Engine | ✅ Match |
| **F02** | FEATURE 2 — The Backtest Integrity & Overfitting Control Engine | ✅ Match |
| **F03** | FEATURE 3 — The Performance Attribution Engine (Brinson) | ✅ Match |
| **F04** | FEATURE 4 — The Portfolio Stress Testing and Scenario Engine | ✅ Match |
| **F05** | FEATURE 5 — The Macro Factor Risk Model and Real-Time Exposure Engine | ✅ Match |
| **F06** | FEATURE 6 — The Market Regime Detection and Regime-Aware Allocation Engine | ✅ Match |
| **F07** | FEATURE 7 — The Liquidity Analytics Engine | ✅ Match |
| **F08** | FEATURE 8 — The Correlation, Diversification and Contagion Network Engine | ✅ Match |
| **F09** | FEATURE 9 — The Alpha Decay and Factor Half-Life Engine | ✅ Match |
| **F10** | FEATURE 10 — The Growth-Optimal Position Sizing and Capital Allocation Engine | ✅ Match |
| **F11** | FEATURE 12 — The Optimal Execution and Transaction Cost Engine | ⚠️ Re-mapped (skip 11) |
| **F12** | FEATURE 13 — The Systemic Risk and Fire-Sale Contagion Engine | ⚠️ Re-mapped |
| **F13** | FEATURE 15 — The Multi-Strategy Portfolio Allocation and Risk Budgeting Engine | ⚠️ Re-mapped (skip 14) |

**Consistency:** ✅ Portfolio_v2 README explicitly documents this re-mapping in its final section. However, other service READMEs (research_v2, factors_v2, pca_v2, screener_v2, volatility_v2) reference portfolio features by their spec numbers (10, 12, 13, 15) — these cross-references remain correct because they refer to the spec, not the internal numbering.

### Service README Checklist Style

Every service README uses a table-of-contents style checklist, but the columns vary:

| Service | Columns |
|---|---|
| **portfolio_v2/README.md** | Feature, Status, Notes |
| **research_v2/DONE.md** | Feature, Status, Current, Future |
| **factors_v2/README.md** | Port, Feature, Area, Target Function, Inputs, Plans, Notes |
| **pca_v2/README.md** | Data, Verification, Cover, Code, Missing Data, Dependency |
| **screener_v2/README.md** | Feature, Status, Notes |
| **volatility_v2/README.md** | Feature, Status, Notes, [Additional Table] |

**Consistency:** ✅ Service-specific tables are appropriately different in structure (different domains need different columns). No unification needed.

### Spec vs Implementation Scope

The root spec describes all 13 features including advanced theoretical components (e.g., Kaplan-Meier survival, reverse stress testing via Mahalanobis distance, partial correlation precision matrix). Portfolio v2's `speed upgrades.md` has actual timing benchmarks (~10s cold, ~1.2s warm). Research_v2's `DONE.md` matches features against the spec numbering. 

**Inconsistency found:** The portfolio features spec has a feature list paragraph (lines 775–777) that references "Feature 11" differently than the headings — Feature 11 in that paragraph corresponds to Systemic Risk / Fire-Sale, but in the spec body that's Feature 13. This is a minor textual confusion in the closing summary.

---

## 2. Spec vs Implementation Docs

### Portfolio_v2 Implementation Coverage

| Feature | Spec Notes | Implementation Checklist |
|---|---|---|
| F01 | 9 optimization objectives, DCC-GARCH, Black-Litterman | ✅ Fully covered in README and speed upgrades |
| F02 | Deflated Sharpe Ratio, bootstrapped, ICS | ✅ Implemented |
| F03 | Brinson attribution, sector-weighted, skill vs luck | ✅ Implemented |
| F04 | Stress tests, reverse stress, Monte Carlo | ✅ Implemented |
| F05 | Macro factor regression, real-time exposures | ✅ Implemented (removed non-price data per spec) |
| F06 | HMM regime detection, regime-conditional optimization | ✅ Implemented |
| F07 | Liquidity analytics, Amihud, LVaR, frontier | ✅ Implemented |
| F08 | Correlation, contagion network, MST, precision matrix | ✅ Implemented |
| F09 | Alpha decay, factor half-life, crowding (ETF proxy) | ✅ Implemented (13F removed per spec) |
| F10 | Kelly sizing, drawdown-constrained, ruin probability | ✅ Implemented |
| F11 (Spec 12) | Almgren-Chriss execution, IS frontier | ✅ Implemented |
| F12 (Spec 13) | Systemic risk, fire-sale contagion, DebtRank | ✅ Implemented |
| F13 (Spec 15) | Multi-strategy allocation, risk budgeting, netting | ✅ Implemented |

### Gaps Documented Across Services

- **portfolio_v2/NOT_DONE.md** (240 lines): Honest register of missing external datasets and proxy fallbacks. Does not claim completeness that doesn't exist.
- **portfolio_v2/missing.md** (445 lines): Performance pass checklist — caching, vectorization, Numba. Points to future work.
- **research_v2/DONE.md**: Features 01–09 and 11 (spec-numbered) are done. Feature 10 (Kelly) is planned. 
- **screener_v2/NOT_POSSIBLE_WITH_CURRENT_DATA.md**: Documents point-in-time, delisted, and persistent storage gaps honestly.
- **screener_v2/missing.md**: Formula engine upgrades, academic strategy additions — forward-looking.
- **ml_v2/speed upgrades.md**: **Empty file** (0 lines). This is a content gap — no performance optimization checklist exists.

### Spec Features Not Yet Covered by Any Service

All 13 features are covered. The complex theoretical components (Kaplan-Meier, reverse stress test, Almgren-Chriss with volume profiles, multi-asset liquidation precision matrix, inter-strategy netting) are documented as implemented in portfolio_v2.

---

## 3. Other Service Docs References

### How Each Service References Portfolio_v2

| Service | References to Portfolio | Pattern |
|---|---|---|
| **research_v2** | `DONE.md`: Features reference spec numbering (Feature 01–09, 11). `review.md`: Architecture assessment. | Links to portfolio feature numbers but not to specific portfolio_v2 files. |
| **factors_v2** | `README.md`: "Portfolio optimization integration" area. `FACTOR_INTELLIGENCE_DEPLOYMENT_BEYOND_PLAN.md`: Cross-system architecture with portfolio_v2. | Factor service treats portfolio_v2 as a consumer of factor intelligence. Architecture diagram references are conceptual. |
| **pca_v2** | `README.md`: Feature 10 (spec numbered) cross-asset PCA for portfolio_v2. `audit.md`: Gap closure against Feature 10. | Direct dependency: pca_v2 provides PCA components for portfolio_v2's Kelly sizing engine. |
| **screener_v2** | `README.md`: S1–S8 feature checklist. No explicit portfolio_v2 references. | Works as independent stock screening service. Data feeds could be consumed by portfolio_v2 but this isn't documented. |
| **ml_v2** | `README.md`: ML-driven portfolio optimizers. References "portfolio_v2" service by name. | ML service mentions portfolio_v2 as a consumer but no cross-document link. |
| **volatility_v2** | `README.md`: "F01–F09 are mapped and matched to portfolio_v2 features; not wired." | Explicit dependency: portfolio_v2 calculations rely on volatility_v2 for vol surfaces. Currently declared as unwired in production. |

### Missing Cross-References

- No service doc links to `portfolio_v2/NOT_DONE.md` for shared gap awareness.
- `ml_v2/speed upgrades.md` is empty — cannot assess whether it references portfolio_v2.
- `screener_v2/FEATURES.md` mentions implementation but not which portfolio features consume screener output.
- `volatility_v2/speed upgrades.md` and `speed upgrade 2 .md` are standalone — no cross-reference to portfolio_v2 performance targets.

---

## 4. Data Dependencies

### External Data Sources Catalogued Across Services

| Data Source | Used By | Dependency |
|---|---|---|
| FRED (DGS10, DGS2, CPIAUCSL, MANEMP, etc.) | portfolio_v2 Feature 5 (future/removed), factors_v2 | Some macro series removed per spec (non-price data). FRED remains for yield curve, credit spreads. |
| Yahoo Finance (^VIX, price data) | portfolio_v2, volatility_v2, research_v2 | Core price feed. |
| NYSE TAQ (via polygon.io or similar) | portfolio_v2 Feature 7 (liquidity), screener_v2 | Liquidity calcs require minute-bar ADV data. |
| SEC EDGAR / 13F filings | portfolio_v2 Feature 9 (removed per spec) | Replaced with ETF AUM growth rate proxies. |
| CRSP / Compustat (via WRDS) | screener_v2 | Point-in-time and delisted data documented as missing in `NOT_POSSIBLE_WITH_CURRENT_DATA.md`. |
| Barron's rankings | screener_v2 `NOT_POSSIBLE_WITH_CURRENT_DATA.md` | Entire dataset unavailable — external database gap. |

### Missing Data Items (Honest Gaps)

- **Point-in-time data** (screener_v2): CRSP/BARRA not available for free
- **Delisted returns** (screener_v2): Survivorship bias not fully addressed
- **Persistent screener storage** (screener_v2): Screened universes don't persist across sessions
- **13F holdings** (portfolio_v2, spec-removed): Crowding proxy switched to ETF AUM
- **CPI / ISM PMI / MANEMP** (portfolio_v2, spec-removed): Non-price macro data removed from Feature 5 scope
- **Bridgewater Growth x Inflation quadrant** (portfolio_v2, spec-removed): Requires CPI — removed

### Dependency Gaps

- **volatility_v2 README** explicitly says "F01–F09 mapped to portfolio_v2; NOT WIRED" — this means portfolio_v2 volatility calculations may be running standalone implementations rather than using the dedicated vol service. This is a significant architectural gap.
- **pca_v2** provides PCA for Feature 10 (Kelly sizing) but the integration point (how portfolio_v2 calls pca_v2) is not documented in either service's README.

---

## 5. Completeness

### Per-File Completeness

| File | Completeness | Notes |
|---|---|---|
| `portfolio features.md` | ✅ Complete (781 lines) | Covers all 13 features with full mathematical specs, custom inputs, metrics, outputs, and additions/removals. |
| `portfolio_v2/README.md` | ✅ Complete (89 lines) | Covers all F01–F13 with status and numbering normalization. |
| `portfolio_v2/NOT_DONE.md` | ✅ Complete (240 lines) | Honest gap register. |
| `portfolio_v2/missing.md` | ✅ Complete (445 lines) | Performance pass checklist. |
| `portfolio_v2/speed upgrades.md` | ⚠️ Partially reviewed (1612 lines) | First 100 lines read; appears exhaustive with timing benchmarks. |
| `research_v2/DONE.md` | ✅ Complete | Features 01–09, 11 done; Feature 10 planned. |
| `research_v2/review.md` | ✅ Complete | Architecture assessment of portfolio v2. |
| `research_v2/speed_optimizations.md` | ⚠️ Partially reviewed (1632 lines) | First 50 lines read; very large file. |
| `factors_v2/README.md` | ✅ Complete (moderate length) | Wiring/ports documentation. |
| `factors_v2/AUDIT.md` | ✅ Complete | Performance kernel review. |
| `factors_v2/FACTOR_INTELLIGENCE_*.md` (3 files) | ✅ Complete | Completion/speed/deployment reports. |
| `pca_v2/README.md` | ✅ Complete | Data verification, missing data checklist. |
| `pca_v2/audit.md` | ✅ Complete | Feature 10 gap closure. |
| `pca_v2/audit code.md` | ✅ Complete | Feature-by-feature spec gap analysis. |
| `screener_v2/README.md` | ✅ Complete | S1–S8 checklist, data inventory. |
| `screener_v2/FEATURES.md` | ✅ Complete | All 8 features, persistence not wired. |
| `screener_v2/NOT_POSSIBLE_WITH_CURRENT_DATA.md` | ✅ Complete | Point-in-time, delisted, persistence gaps. |
| `screener_v2/missing.md` | ✅ Complete | Formula engine upgrades, academic additions. |
| `ml_v2/README.md` | ✅ Complete | Current pass additions, gap closures. |
| `ml_v2/upgrades.md` | ✅ Complete | Frontend UI upgrade checklist. |
| `ml_v2/speed upgrades.md` | ❌ **Empty file** | 0 lines — no content exists. |
| `volatility_v2/README.md` | ✅ Complete | F01–F09 mapped, not wired. |
| `volatility_v2/speed upgrades.md` | ✅ Complete | Numba/Polars/vectorization plan. |
| `volatility_v2/speed upgrade 2 .md` | ✅ Complete | Follow-on performance work. |
| `volatility_v2/vol frontend upgrades.md` | ✅ Complete | Frontend UI checklist. |

### Documented vs Undocumented Integration Points

| Integration | Documented? | Where? |
|---|---|---|
| portfolio_v2 → research_v2 | ⚠️ Partial | research_v2 links to feature numbers but no formal API contract |
| portfolio_v2 → factors_v2 | ⚠️ Partial | factors_v2 architecture diagram references portfolio_v2 |
| portfolio_v2 → pca_v2 | ⚠️ Partial | pca_v2 documents the dependency; no API spec |
| portfolio_v2 → screener_v2 | ❌ Not found | No cross-document reference |
| portfolio_v2 → ml_v2 | ⚠️ Partial | ml_v2 mentions portfolio_v2 by name |
| portfolio_v2 → volatility_v2 | ✅ Explicit | volatility_v2 declares "not wired" status |
| portfolio_v2 → frontend | ⚠️ Partial | ml_v2 and volatility_v2 have frontend upgrade docs; no unified frontend API doc |

### Key Completeness Issues

1. **`ml_v2/speed upgrades.md` is empty** — needs content or should be deleted.
2. **volatility_v2 integration not wired** — portfolio_v2 is live but vol service isn't connected; the actual vol calculations in portfolio_v2 may duplicate or bypass the vol service entirely.
3. **No formal API contract docs** — all services document their features but none documents how other services call them (endpoints, serialization, auth).
4. **Frontend API surface undocumented** — `ml_v2/upgrades.md` and `volatility_v2/vol frontend upgrades.md` list UI features but there's no shared API doc for the frontend-to-backend contract.
5. **Research_v2's missing Feature 10** is documented as "planned" without a timeline or external blocker note.

---

## Summary of Recommendations

1. Add content to `ml_v2/speed upgrades.md` or remove it.
2. Wire volatility_v2 to portfolio_v2 or document the standalone vol implementation being used.
3. Add cross-references from service READMEs to `portfolio_v2/NOT_DONE.md` for shared gap awareness.
4. Document frontend-to-backend API contracts in a single location.
5. Add API endpoint documentation per service for cross-service integration.
6. Minor: Fix the Feature 11/13 reference inconsistency in the spec's closing summary paragraph.
7. Document the portfolio_v2 → screener_v2 data flow if screener outputs are consumed by portfolio features.
