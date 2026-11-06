# SELL-10 Studio: Sellability Scoring of 6 Workspace Modes

Date: 2026-09-29. Scope: read-only review; no code changed.
Sources: `frontend/src/components/studio/*` (DevelopView, TearsheetView, ValidateView, StressView, AdvancedValidationView, ReplayView, ComposerView, PaperView, develop/, shell/StudioModeStage), `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md` P5/P6/P7+P14/P8/P13/P12 definitions. Competitor grounding via web search 2026-09-29 (QuantConnect pricing page, TradingView pricing page, Zerve 2026 backtesting-platform landscape, Bloomberg Terminal/PORT pricing reporting).

## Rubric (per mode, 1-5 each, 40 max)

- existence: does the capability really work today (not stub/demo)?
- parity: how it stands vs the best named rival for that job.
- WTP lift: would a buyer pay more because of it?
- habit: does it drive daily/weekly reuse?
- trust cost: LOW friction scores HIGH (5 = buyer trusts it immediately; 1 = claims need verification work).
- distribution: can we get it in front of buyers cheaply?
- moat: how hard is it to clone?
- bundle fit: does it make the rest of Studio worth more?

Verdicts: >=30 sell now, 22-29 fix-then-sell, <22 hide/cut.

## Competitor baseline used for parity

| Rival | What it is | Price anchor 2026 | Where it beats us | Where we beat it |
|---|---|---|---|---|
| VS Code + Jupyter | Free editor + notebooks, Copilot/agents, backtest-manager extensions | $0 | Editing, completions, debugger, ecosystem | Quant guardrails (preflight, canonical metrics, verdict); VS Code enforces nothing |
| QuantConnect Lean/Research | Cloud Research + backtest + optimize + paper + live, same code path; LEAN open source | Free to ~$300/mo tiers; paper trading on paid plans; $100k virtual account | Live datafeed paper trading, broker integrations, optimization cloud, scale | Deterministic promotion verdict + hash-chain audit + certification bundle; explicit unavailable-not-zero truth; reference-only report recipes |
| TradingView Pine/strategy tester | Pine v6 strategies, basic/advanced report metrics, CSV/XLSX export, Bar Replay, simulated paper trading | $0 / $12.95 / $29.95 / $59.95 / $199.95 per mo (annual billing) | Distribution (100M traders), charting, Bar Replay polish, community scripts | Walk-forward/MC/sensitivity/PSR-DSR/certification (TV has none); causal replay with compat gates; cost-drag truth |
| Bloomberg PORT/Launchpad/BQuant | Terminal portfolio + risk analytics, BQuant python; unmatched liquid-market data | ~$24,000-31,980/yr/seat (~$2.6k/mo) | Data, PORT risk, enterprise trust | Price (3 orders of magnitude), walk-forward-first validation, paper governance ledger, deterministic exports |

## 1. Develop (P5: DevelopView + develop/ProjectTree + ExecutionDock + Editor + PreflightGate + PreExecuteModal)

Capability table (10):

| # | Capability | Exists? | Parity vs best rival (VS Code+Jupyter) | Note |
|---|---|---|---|---|
| D1 | Project tree: tabs, dirty state, save-all, rename/move/duplicate, guarded delete | Yes | Below: no server project API, local-only | File evidence: ProjectTree.jsx, projectStore |
| D2 | Monaco editor + diagnostics/completion/symbol nav/format/templates | Partial (LSP-lite) | Below: full LSP server deferred by design | analyzePythonSource/extractSymbols only |
| D3 | Conflict-safe autosave + backup + rehydrate | Yes (local) | At: for single user; below teams | Server sync open |
| D4 | Diff saved vs working + palette actions | Yes | At | Editor.jsx showDiff |
| D5 | Run file/selection/cell with env picker + quota strip | Yes | At for bounded runs; below for scale | One-shot contract; no persistent kernel |
| D6 | Kernel state/elapsed/cancel/structured logs/provenance | Yes | At for jobs; below for interactive | Fail-closed Docker provider |
| D7 | Variables explorer (typed, paginated) | Yes | Below Jupyter inline richness | 50/page expansion |
| D8 | Data preflight: availability/staleness/corp-actions/lookahead/manifest | Yes | Above: Jupyter enforces none of this | Strongest differentiator in mode |
| D9 | Blocking-errors vs warnings + manifest inspect | Yes | Above | PreExecuteModal |
| D10 | Interactive terminal | No (deferred, one-shot contract) | Below | xterm.js intentionally out |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 4 | 9/10 present; terminal absent by design |
| parity | 2 | Cannot out-edit VS Code; LSP-lite vs real LSP |
| WTP lift | 2 | Nobody switches editors for this; preflight is nice, not decisive |
| habit | 2 | Daily surface but low lock-in; users keep VS Code muscle memory |
| trust cost | 4 | Fail-closed exec + explicit unavailable states |
| distribution | 2 | Crowded; no cheap wedge vs free incumbent |
| moat | 2 | Preflight validators are copyable |
| bundle fit | 4 | Glue: every other mode starts here |
| TOTAL | 22 | fix-then-sell (floor) |

Verdict: FIX-THEN-SELL. Never lead with Develop. Fixes before leading: interactive terminal via bounded channel, server project sync, full LSP or concede editing to VS Code via Lean-style local plugin and keep Develop as the governed-run surface.

## 2. Results (P6: TearsheetView + results/VirtualTradeLedger)

Capability table (8):

| # | Capability | Exists? | Parity vs best rival | Note |
|---|---|---|---|---|
| R1 | Summary strip: conventions (252/simple/pop-vol), engine version, currency/calendar, warnings, job ID | Yes | Above TV basic tester; at QC PDF | Methodology per metric |
| R2 | Linked equity/benchmark/underwater/exposure/turnover/cost charts | Yes | At TV; below TV polish | Benchmark overlay + synced ranges |
| R3 | Virtualized trades/orders + event-to-chart nav; fills explicit-unavailable | Partial | At TV export; below QC order plotting | No fill synthesis (truth+) |
| R4 | Attribution: long/short contribution + cost drag; factor/sector unavailable-by-design | Partial | Below PORT/BQuant; above TV (nothing) | No inferred exposure |
| R5 | Diagnostics: quantiles/ES/histogram/rolling vol; regime unavailable | Partial | At QC; above TV | Regime labels missing |
| R6 | A/B compare with timestamp/convention compat gate + refusal reasons | Yes | Above everyone (QC/TV overlay without gates) | Ghost curve suppressed on mismatch |
| R7 | Metric-to-source traceability + methodology | Yes | Above | CSV carries value/unit/status/methodology |
| R8 | Exports CSV/JSON/HTML-print-PDF; Arrow minimal/deferred | Partial | At QC PDF; above TV XLSX on provenance | Deterministic; reconcile with screen |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 4 | Core truthful; attribution/regime partial by design |
| parity | 4 | Beats TV tester on truth; matches QC report, under PORT on attribution |
| WTP lift | 4 | Traceable numbers are what funds pay for |
| habit | 4 | Every run ends here |
| trust cost | 5 | Unavailable-not-zero is the trust moat; nothing to verify away |
| distribution | 3 | Demo-able in one screenshot; needs sample reports as lead magnets |
| moat | 3 | Compat-gated compare + provenance chain; clonable with effort |
| bundle fit | 5 | Feeds Validate, Replay, Compose, Paper |
| TOTAL | 32 | SELL NOW |

Verdict: SELL NOW. Lead demo: run A/B compare with a deliberately mismatched artifact and show the refusal, then the reconciling export.

## 3. Validate (P7 ValidateView+StressView + P14 AdvancedValidationView; certification bundle)

Capability table (10):

| # | Capability | Exists? | Parity vs best rival | Note |
|---|---|---|---|---|
| V1 | Walk-forward expanding folds + purge/embargo + exact bounds | Yes | Above QC/TV (neither first-class) | Leakage tests pass |
| V2 | Monte Carlo: Gaussian / IID bootstrap / block bootstrap, seeded, assumptions returned | Yes | Above (TV none; QC optimization is not this) | 10k-path budget |
| V3 | Sensitivity grid 1D/2D + table + Canvas2D heatmap | Yes | Above (no rival ships this in-workflow) | 100-cell budget, no 3D |
| V4 | Scenarios: cost/missing/delay real; liquidity/regime/adversarial named skips | Partial | Above (named skips beat silent gaps) | Honest partial |
| V5 | Durable jobs: pre-dispatch work estimate, budget cap, SSE resume, cancel-wins | Yes | At QC cloud; above TV | Same queue as execution |
| V6 | Editable-threshold verdict + promote/reject/override | Yes | Above everyone | Rules inspectable |
| V7 | Append-only hash-chain promotion audit | Yes | Above everyone | drift-detectable |
| V8 | Probabilistic/deflated Sharpe + trial penalty + instability | Yes | Above (institutional-grade, opt-in) | P14 formulas + fixtures |
| V9 | Capacity/liquidity/spread/impact/borrow/turnover feasibility; substitution test | Partial (supplied inputs; skips named) | Above BQuant-adjacent; below PORT data richness | No inferred inputs |
| V10 | Content-addressed certification bundle + reproduction endpoint | Yes | Above everyone | Source/validation/bundle hash check |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 5 | Complete incl. advanced panel; skips explicit |
| parity | 5 | No rival has verdict+audit+certification in one loop |
| WTP lift | 5 | This is the buying reason for funds |
| habit | 3 | Episodic (pre-promotion), not daily |
| trust cost | 5 | Thresholds visible, skips named, repro endpoint |
| distribution | 3 | Technical sale; needs education content |
| moat | 5 | Hash-chain audit + certification + leakage controls as a system |
| bundle fit | 5 | Gates Paper; justifies Results; feeds Compose |
| TOTAL | 36 | SELL NOW |

Verdict: SELL NOW. Crown jewel. Price on this mode.

## 4. Replay (P8: ReplayView + studioReplay lib)

Capability table (6):

| # | Capability | Exists? | Parity vs best rival (TV Bar Replay) | Note |
|---|---|---|---|---|
| RP1 | Immutable ordered event schema from persisted artifact (no rerun) | Yes | Above (TV replays bars; we replay run truth) | Frozen payloads, stable IDs |
| RP2 | Synced timeline/chart/position/logs + position-at-cursor | Yes | At | O/X timeline + job-log panel |
| RP3 | Step/jump/breakpoint predicate/speed/filter/search | Yes | At TV Bar Replay controls | Conditional breakpoint pauses autoplay |
| RP4 | Run-to-run divergence with compat gate | Yes | Above (TV has none across runs) | First-divergent-event report |
| RP5 | Deep links: run/event/time/filter/query | Yes | Above | URL state round-trips |
| RP6 | Causal chain signal->position->P&L; fills explicit-unavailable | Partial | Below QC order plotting on fills | No synthesis; order/fill events need artifacts |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 4 | Deterministic core done; fill chain partial |
| parity | 3 | TV Bar Replay more polished; ours more truthful + divergence |
| WTP lift | 3 | Supports the sale; rarely the sale |
| habit | 3 | Debugging sessions, not daily |
| trust cost | 4 | No regenerated approximations; limits stated |
| distribution | 3 | Great demo GIFs; deep links shareable |
| moat | 3 | Divergence + deep links; replay itself clonable |
| bundle fit | 4 | Makes Results/Validate evidence explorable |
| TOTAL | 27 | FIX-THEN-SELL |

Verdict: FIX-THEN-SELL. Fixes: real order/fill artifacts to complete RP6, chart-polish pass to match Bar Replay feel. Ship inside bundle; do not price standalone.

## 5. Compose (P13: ComposerView + reports backend)

Capability table (7):

| # | Capability | Exists? | Parity vs best rival (QC PDF report) | Note |
|---|---|---|---|---|
| C1 | Reference-only recipes (no embedded data copies) | Yes | Above (QC bakes reports; we reference artifacts) | Reopen reflects live artifact |
| C2 | Resizable layouts + saved views + linked selections | Yes | Above | Keyboard spans, composer store |
| C3 | Narrative blocks with citations + metric-path resolution | Yes | Above (nobody cites live metrics) | Fingerprinted payload |
| C4 | Research notes / decision journal linked to runs | Yes | Above | Durable, context-bound |
| C5 | 4 server report templates | Yes | At | Strategy/validation/portfolio/paper |
| C6 | Deterministic HTML/CSV/JSON + print-PDF + per-block PNG + minimal Arrow | Partial | At QC PDF on coverage; above on determinism | Full Arrow IPC deferred |
| C7 | FORMULAS registry + manifests/warnings/version footer in exports | Yes | Above | Reports readable without Studio |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 4 | Composition + exports real; Arrow full deferred |
| parity | 4 | Reference-only + citations beat QC baked PDF |
| WTP lift | 3 | Closes institutional deals; solo quants care less |
| habit | 2 | Episodic (reviews, audits, fundraising) |
| trust cost | 4 | Deterministic bytes + hashes; reproducible |
| distribution | 3 | Sample reports are excellent lead magnets |
| moat | 4 | Reference-only model + FORMULAS registry + certification tie-in |
| bundle fit | 5 | Turns every other mode into a shippable artifact |
| TOTAL | 29 | FIX-THEN-SELL (top of band, nearest to sell) |

Verdict: FIX-THEN-SELL, one polish away from sell-now: finish full Arrow IPC + a genuinely beautiful print-PDF template, then pair with Validate certification as the audit package.

## 6. Paper (P12: PaperView + paper backend)

Capability table (7):

| # | Capability | Exists? | Parity vs best rival (QC paper trading) | Note |
|---|---|---|---|---|
| P1 | Gated promotion: version + passing WF job + promote audit required | Yes | Above (QC lets anything paper-trade) | The governance wedge |
| P2 | Deployment config: schedule/universe/limits/kill-switch (actor+reason) | Yes | At QC controls; above TV sim | Audited engage/release |
| P3 | Causal ledger signal->intended->submitted->fill->position->valuation + hash chain | Yes | Above on causality; below on realism | Supplied observations only |
| P4 | Reconciliation: intended-vs-fill slippage classification | Yes | Above (QC does not classify divergence) | No synthesized fills |
| P5 | Alerts: limit/stale/missing/rejected + auto-halt | Yes | At | Rejection creates linked alert |
| P6 | Trace endpoint position->signal; lifecycle armed/running/halted | Yes | Above on auditability | Restart-recoverable SQLite store |
| P7 | Broker adapter / fill simulator / scheduled runner / price source | No (out of scope by design) | Below QC live datafeed + brokers; below TV sim trading | Records observations; makes no broker call |

Rubric:

| Criterion | Score | Reason |
|---|---|---|
| existence | 4 | Governance loop complete; execution realism absent by design |
| parity | 2 | Loses any realism shootout vs QC/TV sim |
| WTP lift | 3 | Governance buyers pay; tinkerers bounce on P7 |
| habit | 3 | Watching paper runs is sticky if runs are live |
| trust cost | 4 | States what it does not do; kill-switch tested |
| distribution | 2 | Hard story without live broker logos |
| moat | 3 | Gated-promotion + causal ledger; simulator easy for others |
| bundle fit | 4 | Closes Develop->Results->Validate->Paper loop |
| TOTAL | 25 | FIX-THEN-SELL |

Verdict: FIX-THEN-SELL. Two paths: (a) add a simulator-lite + one real broker paper adapter (Alpaca/IB) to reach parity, or (b) reposition as paper-governance for funds that already execute elsewhere. Do not sell as a trading platform today.

## Scoreboard

| Mode | Total /40 | Verdict | Lead with? |
|---|---|---|---|
| Validate | 36 | SELL NOW | Yes: price anchor |
| Results | 32 | SELL NOW | Yes: demo hook |
| Compose | 29 | fix-then-sell | Bundle sweetener; 1 polish from sell |
| Replay | 27 | fix-then-sell | Inside bundle |
| Paper | 25 | fix-then-sell | Governance angle only |
| Develop | 22 | fix-then-sell (floor) | Never lead; glue |

Counts: 6 modes scored, 48 capabilities inventoried (10+8+10+6+7+7), 2 sell-now, 4 fix-then-sell, 0 hide/cut. Nothing scores <22, so no mode is cut; Develop at exactly 22 must not be demoed standalone.

## Top 3 money capabilities (what actually lifts WTP)

1. Validate promotion verdict + hash-chain audit + certification bundle with reproduction endpoint (V6/V7/V10). Nobody else sells a drift-detectable go/no-go record. This is the price anchor.
2. Results canonical traceable metrics + compat-gated A/B compare + deterministic exports (R1/R6/R7/R8). Turns "trust me" backtests into auditable numbers; demo the refusal-on-mismatch.
3. Paper gated deployment + causal ledger + slippage reconciliation + kill-switch (P1/P3/P4). The only paper loop that enforces validation before deployment; sell as governance, not execution.

## Bundle and price

Rival anchors: TradingView $13-60/mo, QuantConnect free to ~$300/mo, Bloomberg ~$2.6k/mo/seat. We sit between QC and Bloomberg: cheaper than data-terminal, more truthful than charting tools.

- Studio Truth Bundle $49/mo (solo): Results + Replay + Compose. Sells against TV Premium ($60): our reports reconcile, theirs do not.
- Studio Promotion Bundle $149/mo (pro): + Validate full (advanced evidence, certification) + Paper governance. Sells against QC tiers + home-grown review: the verdict/audit is the feature.
- Team/Audit $499/mo: everything + multi-user audit log, retention controls, sample certification pack. Sells against Bloomberg-adjacent audit pain at 1/5 the seat logic (per-team, not per-seat).
- Do not price Develop standalone; do not price Paper as execution.

## Distribution moves (cheapest first)

1. Publish 3 sample certification bundles + deterministic HTML reports as lead magnets (Compose C6/C7 does the work; SEO "walk-forward certification template").
2. Demo clip: A/B compare refusal on mismatched artifacts (R6) + verdict override with actor/rationale (V6). 90 seconds, posts everywhere quants argue about overfit.
3. Jupyter/VS Code bridge (concede editing): export run artifact + import into notebooks; Lean-style local plugin later. Turns Develop weakness into funnel.
4. QuantConnect comparison page: same-code-backtest vs our promotion gate; target "QuantConnect validation" search intent.
5. TradingView refugee content: "what the strategy tester does not tell you" with cost-drag and regime-unavailable honesty (R4/R5).
6. Fund-outreach pilot: one audit-ready certification pack for a real strategy; logo beats ads.

## Path (ordered, minimal)

1. Now: sell Results + Validate as the Truth/Promotion bundle; demo R6 refusal + V6/V7/V10 certification. Publish sample reports (move 1).
2. Next (Compose to 30+): full Arrow IPC + beautiful print-PDF template + one-click certification-to-report flow. Compose joins sell-now.
3. Then (Paper decision): simulator-lite + one broker paper adapter (Alpaca or IB) OR commit to governance-only positioning with runner-agnostic import. Until then, Paper rides in Pro bundle, never standalone.
4. Then (Replay to 30+): real order/fill artifacts complete RP6 + Bar-Replay-feel polish.
5. Last (Develop off the floor): terminal via bounded channel + server project sync; in parallel ship the VS Code/Jupyter bridge so Develop stops competing with free editors.
6. Never: cut nothing today; revisit only if Develop stays at 22 after the bridge ships (then hide it as a tab and make VS Code the primary editor).
