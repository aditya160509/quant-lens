# Studio Dev backend tasks

The [numbered Dev Ideas catalogue](DEV_IDEAS.md#feature-catalogue-detailed) has **9 ideas with backend work remaining** as of 2026-11-21. Seven are in the active backlog and two are gated on owner approval. Count one task per numbered idea, including partial features that need a backend change. This count is for the numbered catalogue. The broader [Studio checklist](CHECKLIST.md), IDE feature catalogue and Results wishlist have their own scope.

Work in backend code and backend tests. For a feature that also needs UI, deliver and verify the backend contract and record the remaining UI dependency here. Keep existing API behavior compatible.

## Active backlog (7)

- [ ] **#12 Run a selection over a date range.** Execute a selected expression, function or block against the requested date window using the existing sandbox and historical data loader. Return typed values or tables without changing the strategy.
- [ ] **#13 Reactive cells.** Use the cell parser and execution path to identify reads and writes, propagate staleness and run affected cells in dependency order.
- [ ] **#11 Research cell state.** Existing cells run through `/build/cells` and can load market data. The remaining backend work is a defined way to pass research state into a strategy preview while preserving run isolation and reproducibility.
- [ ] **#14 SQL cells.** Provide bounded, read-only queries against the existing approved data store and return typed rows. Any new dependency needs separate approval.
- [ ] **#17 Snippet and indicator library.** Extend existing snippet storage for tags and workspace sharing, and support testing a snippet in the sandbox before insertion.
- [ ] **#18 Starter gallery data.** Extend cached starter statistics with a compact equity series and the starter's snippet references.
- [ ] **#20 Chart-bar review threads.** Extend existing line comments with symbol, timeframe and bar timestamp anchors, plus resolve and reopen state.

## Owner-gated backlog (2)

- [ ] **#23 Paper trading divergence.** Compare paper fills and equity with the corresponding backtest and expose divergence diagnostics and thresholds.
- [ ] **#24 Live status and kill switch.** Verify coverage of the existing live APIs and fill any gaps in status and control contracts after the owner approves live-trading scope.

The debugger locals trade-navigation link (#16), inline cell output (#11) and pop-outs (#28) are UI work. AI ideas #21–22 are parked in Dev Ideas.
