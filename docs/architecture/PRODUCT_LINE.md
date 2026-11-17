# Product line

Decided 2026-11-17 (owner). One job per section; shared engines underneath.

| Section | Job | Who |
|---|---|---|
| Research | Ask a question of the market and get a tested answer | Everyone |
| Screener | Find names | Everyone |
| Factors (includes PCA) | Understand what drives returns | Investors, quants |
| Volatility | Understand risk regimes | Investors, traders |
| Studio | Build, prove and run a strategy | System builders |
| Portfolio | Manage what you own | Every investor |

## Portfolio vs Studio › Portfolio

| | Studio › Portfolio | Portfolio (its own section) |
|---|---|---|
| Question | "How do I combine my strategies?" | "What do I own, how risky is it, what should I change?" |
| Inputs | Backtested strategy equity curves | Holdings: tickers, shares, cost basis, CSV or broker import |
| User | Someone who builds systems | Every investor, including people who never write a rule |
| Outputs | Allocation across strategies, combined grade, send to Validate | Risk contribution, factor exposure, stress, drawdowns, rebalance trades, what-if, attribution vs benchmark |

Decisions:
- **Portfolio is its own full section.** It is the bigger audience and the main front door. Inside Studio it would be hidden behind a name that means "build strategies".
- **Studio › Portfolio stays scoped** to combining strategies: finish the combined grade and P-3 (send to Validate), nothing more.
- **One engine.** Covariance, risk parity, HRP, max Sharpe, risk contribution and stress are built once as a shared module (from `studio_v3/core/portfolio.py`). Both front ends use it; `portfolio_v2` moves onto it. Its 42-item checklist is re-cut against the shared engine before building.
- **The links between them:**
  - A strategy running live in Studio appears in Portfolio as a holding.
  - "Test a rule on these holdings" opens Studio with the holdings as the universe.
  - Factor exposure in Portfolio comes from the Factors lab.

## Other decisions on 2026-11-17

- PCA is a section of Factors, not its own lab (`plans/FACTORS_CHECKLIST.md`).
- Widget workspace: cut for now; revisit after launch.
- Chart system: shrink to export and annotations; no per-chart styling panel.
- Order after Studio:
  1. Data refresh and the daily update job
  2. Factors (with PCA)
  3. Volatility
  4. Portfolio
  5. Shared kit
  6. Screener and ML leftovers
  7. End-to-end tests and deploy
- Missing and needed: accounts and auth, CI with end-to-end tests, a hosted deploy plan.
