# Studio: every feature at its peak (merged)

This file merges two independent research passes into one ranked target list. Full specs live in the passes:
- [FEATURES_PEAK_A.md](../research/FEATURES_PEAK_A.md): a research agent, 904 lines. Competitor notes are marked [R] when read from docs and [K] when from product knowledge.
- [FEATURES_PEAK_B.md](../research/FEATURES_PEAK_B.md): my pass, 572 lines. Part I is the Python IDE; Part II covers every page.

Where the two disagree, B's concrete API and defaults win and A's breadth is kept. Every item is checked against `standards/CODE_STANDARDS.md` and `standards/UI_GUIDE.md` when built. Data limits in `DECISIONS.md` still apply: daily bars only, no live use until the data refresh, and fundamentals from 2021.

## Ranked target list (A's top 60, with B-only additions marked +B)

1. Immutable, reproducible run records with one-click Reproduce.
2. Same engine and execution model across backtest, paper, live.
3. One-click Validate scorecard with editable policy (pass/warn/fail with reasons).
4. Walk-forward (anchored/rolling) plus Walk-Forward Matrix with 3D surface.
5. Trade-list Monte Carlo (reshuffle, resample, skip trades) with confidence-level table.
6. Price-path robustness: noise test, Vs Random, Vs Shifted, Vs Others, permutation.
7. Deflated Sharpe and trials counter carried from Optimise into Validate.
8. Look-ahead protection by API design, lint, and runtime guard.
9. Declarative params shared by blocks, formula, code, optimiser.
10. Optimiser with grid/random/Bayesian/genetic, constraints, multi-objective, no 3-param cap.
11. Parameter heat maps with stability (plateau) scoring and "pick plateau" tool.
12. Hidden hold-out period enforced at project or team level.
13. Execution model panel with presets and custom hooks (fees, slippage, fills, borrow, margin).
14. Intrabar fill fidelity levels with ambiguous-bar count shown.
15. Live vs backtest divergence monitor with expected-band overlay.
16. Promotion gates: backtest -> validate -> paper -> small live -> live, with editable checklists.
17. Kill switches and automatic risk triggers (daily loss, DD, stale data, broker mismatch).
18. Position reconciliation and crash recovery in live.
19. Broker adapters (IB, Alpaca, Tradier, Schwab, Tastytrade, crypto) with connection status and disconnect handling.
20. Signals-only mode with took/skipped tracking.
21. Alert rule builder with webhook templating, escalation, quiet hours, test button.
22. Four authoring modes (blocks, formula, Python, English) on one document model.
23. English-to-blocks with explicit interpretation confirmation before any run.
24. Block editor with Any/All nested conditions, live "where did this fire" chart preview.
25. Degrees-of-freedom / complexity meter while building.
26. Full Monaco language server with Studio stubs and domain diagnostics.
27. Time-travel debugger on finished backtests plus live-step debugger with logpoints.
28. Structured logs panel with click-to-bar and click-to-line.
29. Plot API with panes, markers, regions, data window, decimation (no silent quota failure).
30. Backtest report with 60+ stats, customisable tiles, range-brush recompute.
31. Trades table of 100k+ rows with MAE/MFE, tags, jump-to-chart and jump-to-code.
32. Costs tab with sensitivity slider (0x to 3x).
33. Compare 2 to 6 runs: equity, stats, params, code, execution model.
34. Warnings engine on every report (few trades, edge params, top-trade dependence, cost drag).
35. Version timeline with metrics per version, diff, branches, restore.
36. Portfolio builder with risk parity/HRP/min-variance/threshold rebalancing and constraints.
37. Portfolio analytics: marginal risk contribution, drawdown overlap, sleeve drop-out test.
38. Walk-forward allocation test (weights estimated out-of-sample).
39. Universe library, point-in-time, with survivorship badge and pinned versions.
40. Cost profile library with presets and impact comparison.
41. Data catalog with gaps, adjustments, and a per-run data quality report.
42. Multi-timeframe access with only "last completed bar" semantics.
43. Indicator registry (150+) driving autocomplete, blocks, formulas, optimiser ranges, warm-up.
44. Indicator lab with live tuning on chart, no backtest needed.
45. One chart engine for every page (WebGL, 1M bars) with multi-chart sync options.
46. Drawings that convert to alerts and block conditions.
47. Replay mode including blind replay and strategy-stepped replay.
48. Strategy overlay on chart with per-trade "why it fired" card.
49. Command palette and quick open spanning all pages and objects.
50. Fully remappable keybindings with VS Code/Vim/JetBrains presets.
51. Settings with scopes (user/project/run), search, sync, and admin locks.
52. Dockable saved layouts per task (Coding, Review, Live monitor).
53. Home table with status pipeline chips, sparkline, stale-run badge, bulk actions.
54. Notebook tab sharing data and engine, `load_run` and `optimise` helpers.
55. AI assistant with diff-approval, critic mode citing lines and numbers.
56. AI experiment agent running variants as branches under a budget.
57. Agents library with budgets, schedules, and no live-order permission.
58. Libraries with version pinning, auto docs, tested examples, and forkable templates.
59. Audit log and roles (viewer/commenter/editor/owner), comments anchored to code and bars.
60. Performance and compute manager: queue, ETA, quotas, streaming results, cancel with partial results.

### +B: in pass B but not in A's list

61. Portfolio-mode Python API (`on_data`, `target_weights`, brackets with OCA, pyramiding, risk-rule class attributes, `rank` and `zscore`), per B §4.
62. In-browser Pyright with Studio stubs, so completion covers user classes (QuantConnect does not).
63. Inline values: formula values next to `ctx.value`, true-rate next to `ctx.rule`, parameter values next to `ctx.param` (B §2, §17).
64. CodeLens run and debug from a line, a date or a symbol.
65. Data breakpoints (pause on the first order, or on an equity drop) and step back one bar.
66. Single editing session per strategy with take-over (fixes QuantConnect's two-tab desync).
67. QuantConnect-algorithm import shim mapping `QCAlgorithm` calls to `ctx`, with the unmapped calls listed.
68. Trial counter in the IDE status bar ("trial 14 on this idea").
69. Composer-style tree blocks (if/else, filter, weight) with a live true-rate on each block.
70. Rule generation (SQX / Build Alpha) where every candidate counts in the trial ledger.
71. Run-ups table, and a capital-efficiency tab (TradingView).
72. Walk-forward optimisation with stitched out-of-sample periods; custom objective as a formula; parallel coordinates.
73. Validation on unseen symbols (train on half the universe) and pass bars per regime.
74. Portfolio netting across members, efficient frontier, crisis stress.
75. Shadow book in Live (frozen version against paper, per-trade explanation of drift).
76. Formula-to-indicator pane on Chart, so Build and Chart share one language.

## Avoid (both passes)

- Results that can't be reproduced, silent truncation, and hidden fill and cost assumptions.
- Quotas that stop a run (QuantConnect charts, TradingView's 9,000-trade cap). Studio decimates and shows a truncation row instead.
- No verdict: SQX and Build Alpha let users pick the tests that pass. Studio has one locked policy and one scorecard.
- Intrabar guesswork without saying so. Studio uses a stated worst case: the stop fills first.
- Optimisers capped at 3 parameters, and optimiser runs that can't be compared.
- Debuggers that need a breakpoint to start, or none at all (Pine).
- Two browser tabs editing one project, which fall out of sync (QuantConnect).
- AI edits applied without lint, validation and diff approval.
- Desktop-locked settings and results (AmiBroker, NinjaTrader, MT5).
- Easy-but-opaque block builders that hide lookback and rebalance assumptions (Composer).

## How this list is used

Pages are finished one at a time. For each page, take the items above that belong to it, build them to the spec in A or B, check them against the standards, verify in the browser at 1440 and 390px in light and dark, then commit. Items needing data we lack are recorded in `DECISIONS.md`, never faked.
