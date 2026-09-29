# P1-W2 canonical metrics execution

Date: 2026-09-12

Canonical performance metrics now live in `backend/app/services/studio/metrics.py`. The calculator documents simple-return, geometric annualization, population-volatility, risk-free-rate, drawdown, and benchmark conventions. Every metric carries a value, unit, availability status, sample size, and methodology. Missing inputs yield `null` with warnings rather than numeric zero.

The deterministic fixture suite covers absolute performance, trade metrics, missing values, invalid equity, aligned benchmark metrics, seeded Monte Carlo output, and observed walk-forward folds. Numerical fixture comparisons use absolute tolerance `1e-10`.
