# Page log

One entry per page when it closes: what shipped, what was checked, what is still open. Newest first. Counts come from `CHECKLIST.md`.

## Home (`/studio`): 12 / 25, in progress

### Decisions

- **QuantConnect import moved to Build (B-163).** An AST shim turned simple QuantConnect algorithms into Studio rules (indicators, set_holdings, liquidate; unconverted lines listed). Removed from Home on 2026-11-18: it covered only simple rule strategies, exits came out as `if_else(cond, 0, 1)`, and a competitor's name on Home was not worth a half-working feature. Comes back in the Python editor once Python strategies run, keeping the user's code instead of converting it to rules. The removed version is in commit `4651300`.

## Portfolio (`/studio/portfolio`): 25 / 28, closed 2026-11-18

### Shipped

- **Methods:** equal, inverse vol, risk parity, HRP, max Sharpe, max diversification, minimum variance, shrunk minimum variance, mean-variance with shrinkage, capped Kelly, member momentum, drawdown throttle, fixed.
- **Rebalancing:** fixed, quarterly, rotation, threshold (corridor and minimum trade).
- **Constraints:** max weight, max correlation, cash reserve, minimum members, per-symbol and per-sector caps, gross and net limits, leverage cap, ban list.
- **Sleeves:** enable, start date, volatility target, capital share; a saved book can be a member (`book_ids`).
- **Regime weighting** on a benchmark rule.
- **Risk tab:** diversification and stress, efficient frontier, share of risk, crisis windows, drop-one, capacity by sleeve, sector exposure, gross/net/beta/cash/margin on the last bar.
- **Correlation tab:** matrix, overlap, clusters, marginal contribution, 6-month rolling correlation, drawdown overlap.
- **Grade tab:** combined grade from the Validate tiles.
- **Paper tab:** freeze the mix as one paper book, netted orders for today, paper return and per-member attribution (`core/book.py`, `/api/studio-v3/books`).
- **Netting in execution:** `net_execution` charges cost on netted trades (approximate; scale-outs ignored).
- **Defaults:** Study rail › Defaults › Make these my defaults.

### Checked

- Real run on Trend 100 v1, RSI(2) dip v2, SMA cross v1: +98%, grade B, about 2.5–3 s.
- Paper book from 2025-06-01: +25.0%, Sharpe 2.16; test books deleted from the store.
- Netting on: saves about $24 a year on $100k (members rarely trade against each other).
- Browser at 1440, 1024 and 375 px, dark and light; no horizontal overflow; console clean apart from an unrelated 402.
- Screenshots: `docs/studio/screens/portfolio-1440.png`, `portfolio-1024.png`.
- 100 backend tests in `tests/test_studio_v3_*.py`; ruff and tsc clean.

### UI guide and canon pass

Fixed on this page; the shared ones apply to every Studio page:

- Open tab kept in the URL (`?tab=`), restored on refresh (shared `FeatureView`).
- No entrance motion: hero figure and lines, result fade, card stagger on tab switch, panel slide on load (shared).
- Hero lines were cut short by a `pathLength` animation under `non-scaling-stroke` (shared `Hero`).
- Feature header wraps tools under the title when the centre column is narrow (shared).
- Inspect rail opens with its outputs list instead of an empty panel (shared).
- KPI strip fits four in one row (shared `.kpis`).
- Grade shown once: the verdict chip is hidden on Portfolio.
- Exposure, net and gross columns format as percent (shared `format.ts`).
- Paper view: no middle-dot meta string, spacing on the scale.
- Every menu trigger closes its menu on a second click (shared `PopMenu`); the inspector toggle no longer reopens itself mid-animation (shared `panels.ts`).
- One Run button: the header's hides on desktop while the inspector is open, and the inspector shows Run in both Study and Inspect.
- Tables stay tables down to 400px; label-value cards are for phones only.
- Symbol search is a full popup: company, type and exchange per row, exchange filters, several adds without closing, ticks on names already added.
- CAGR and volatility columns format as percent.
- Menus (View, More, dropdowns) measure themselves, stay inside the window and render at the shell root, so sticky bars never cover them (shared `PopMenu`).
- Cluster tree drawn sideways: names on the left, distance along the bottom, height from the leaf count (shared `Dendrogram`).
- Tables of 12 rows or fewer have no toolbar row; row hover covers the first column (shared `DataTable`).
- Sharpe, correlation and beta to 2 places; share columns (both active, overlap) as percent (shared `format.ts`).
- Chart drawing tools show on hover, focus or while in use (shared `TimeSeries`).
- Pair tables say Strategy and Paired with, not A and B.

### Next: table and chart pass on every card

- Line charts, bars and heatmaps against `UI_GUIDE.md` §5: axis ticks, legend placement, card spacing, chart heights; check each in the browser.
- Rolling correlation starts at 0 in 2016 because members have not traded yet; decide whether to start it at the first bar where every member has a position.

### Open

- **P-5:** page controls for sleeves (they are a JSON input today).
- **P-23:** asset class column (all data is US equity).
- **P-22:** multi-currency, blocked by data (no FX series).
- Headline Sharpe (0.60) and KPI Sharpe (0.595) round differently.
- "Combined vs each" card repeats the hero lines; kept for its axes and zoom.
- Opening an old run does not restore its strategy picks; Run then fails until they are ticked (the stale chip shows it).
- Sector exposure is rebuilt from trades and final weights, so it is approximate under quarterly, rotation and threshold rebalancing.
- Custom Python allocation function skipped.
- The netting measure without `net_execution` reads a position count, not per-symbol positions.
