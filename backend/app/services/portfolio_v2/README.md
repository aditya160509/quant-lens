# Portfolio V2 backend

Portfolio V2 serves 13 feature contracts at `/api/labs/portfolio/v2/features` and runs them through a strict, lazy registry. The existing router is mounted by `backend/main.py`.

Read [DONE.md](DONE.md) for the rebuild, estimator definitions, verification commands, and data limitations. It supersedes the original scaffold checklist. The original [feature specification](docs/portfolio%20features.md) remains design history; unsupported outputs are explicitly removed or disclosed in the current manifest.

Routes include synchronous runs, background jobs with status/cancellation, symbol search, validated CSV uploads, and JSON/CSV/LaTeX export. No runtime feature downloads data, generates demonstration returns, substitutes unknown tickers, or converts missing prices into zero returns.

Implementation features 01–10 match specification features 1–10. Implementation 11/12/13 correspond to specification 12/13/15; both identifiers are served in the manifest.

Frontend rebuilding remains reserved for Claude. This backend pass does not change frontend files or legacy Portfolio services.
