# Page log

One entry per page when it closes: what shipped, what was checked, what is still open. Newest first. Counts come from `CHECKLIST.md`.

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
