# Screenshot review log

Review of 2026-11-23. Done items are pushed to main; open items are tracked as RV-1 to RV-22.

## Done
- 90bbd33 2026-11-23 Chart: held-trade shading at 8% so the band no longer hides price
- 1ee1a73 2026-11-23 Build rail: empty Inputs and Outline sections hidden; outline kinds are plain monochrome glyphs with the line number in the tooltip
- 6a9b246 2026-11-23 Build layout: panel tabs that do not fit go into a More menu; code does not wrap by default and inlay hints are muted, smaller and can be turned off; status bar shows the data's last bar, not the clock; runs pill hidden on Build and its dot only marks running or failed. Also commits Workspace.tsx (WorkspaceItems), which DevIDE already imported, so main builds from a clean checkout
- 8250658 2026-11-23 Hold-out: one sealed date from the whole history for every run, so a 5-year quick run can no longer show dates a full run keeps sealed
- 0406ac9 2026-11-23 One basis for trade stats: headline win rate, profit factor and trades count closed trades, open ones shown apart; Tester and Results share one stat strip with a scope line, ratios n/a below 10 trades; Results shows provenance, named benchmark, drawdown strip, idle-period note, side table only when both sides trade; report buttons in the toolbar

## Left to do
Done already and pushed: one basis for trade stats, hold-out leak, provenance line, small-n guard, panel tab overflow, wrap and inlay hints, status bar, runs pill, empty rail sections, table and histogram formatting, held-trade band at 8%. C7 (flush square panes) skipped: it breaks the liquid-glass look.
- [ ] [S] RV-1 Chart: check candle up/down colours match the theme tokens
- [ ] [M] RV-2 Chart: B/X trade markers on the price pane. Vela native indicators cannot emit `trades`; use a script indicator or drawings, else keep the lane marks
- [ ] [S] RV-3 Chart: OHLC legend for the hovered bar
- [ ] [S] RV-4 Chart: drawing rail hides disabled tools and can collapse
- [ ] [S] RV-5 Chart: volume bars coloured by up/down
- [ ] [M] RV-6 Chart: axis tick labels and crosshair label no longer overlap axis labels (Vela internal)
- [ ] [S] RV-7 Results: sticky tabs (Overview, Trades, Orders…)
- [ ] [M] RV-8 Results: Tearsheet and Robustness reachable from Results, not only the report page
- [ ] [M] RV-9 Results open in the right pane beside the code instead of replacing it
- [ ] [S] RV-10 One run vocabulary and one Run menu: Preview, Quick run, Full run
- [ ] [S] RV-11 DataTable: the money rule formats any numeric `value` column with 2 decimals; restrict it so Run settings (e.g. slippage 0.0005) is not shown as 0.00
- [ ] [S] RV-12 DEV_IDEAS: dated chart decision log
- [ ] [S] RV-13 DEV_IDEAS: fix status drift; statuses checked by tests, not by hand
- [ ] [S] RV-14 DEV_IDEAS: freeze rule and quality gates (widths, metrics)
- [ ] [S] RV-15 DEV_IDEAS `results.py` risks: plain-text rendering, size caps, CSV formula injection, determinism, partial failure
- [ ] [S] RV-16 DEV_IDEAS: user-defined optimiser objective logged in the trial ledger; acceptance criteria per item
- [ ] [M] RV-17 Test: RunMetrics contract (backend fields = frontend type)
- [ ] [M] RV-18 Test: QuantStats golden numbers
- [ ] [M] RV-19 Test: visual regression at three window widths plus a clipped-control check
- [ ] [M] RV-20 Accessibility pass on Build and Results
- [ ] [S] RV-21 Empty-data guards on every Results card
- [ ] [S] RV-22 Versioned `viewKey` per strategy so saved layouts survive changes
Still unbuilt from earlier: `results.py` user reports (DEV_IDEAS 2b), editor research items, IDE and terminal items, universe summaries.
