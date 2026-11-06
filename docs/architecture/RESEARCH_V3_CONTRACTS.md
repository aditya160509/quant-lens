# Research build batch: API contracts (frontend ⇄ backend)

Base path is `/api/labs/research/v2`. The scope comes from docs/RESEARCH_PRODUCT_REVIEW_FINAL_BATCH.md:
- In scope: sections B, C1–C4 and E; A1–A6 except the Python SDK, the REST API and scheduled re-runs; A7b (Assaying Anomalies protocol and batch screening); and A7 without AI (template explainers and catalog lookup).
- Out of scope: A8 pricing and the research agent.

The jobs API is unchanged everywhere: `POST .../jobs` returns `{job_id,status}`, and `GET /jobs/{id}` returns `{status, progress, result, error}`.

## 1. Signals (agent S)
- `GET /signals/operators` → `[{name, args:[str], doc, example, category}]`
- `GET /signals/fields` → `[{name, source:"price"|"fundamental"|"derived", doc, coverage:0..1}]`
- `POST /signals/validate` `{expr}` →
  - `{ok:true, preview:{n_names, months, histogram:[{x0,x1,count}], coverage:[{month,share}], corr_known:[{name,corr}]}}`
  - or `{ok:false, error:{message, start, end}}`
- `GET /signals/library` → `[{id, name, category, formula, citation, year, expected_sign:1|-1}]`. At least 40 classic anomalies written in the formula language and computable from local data.
- `POST /signals/saved` `{name, expr, project_id?}` → `{id, version}`; saving an existing name adds a version.
- `GET /signals/saved` → `[{id,name,latest_version,updated_at}]`
- `GET /signals/saved/{id}` → `{id,name,versions:[{version,expr,created_at}]}`
- `POST /signals/combine` `{exprs:[str], method:"equal"|"ic"|"inverse_variance"|"rank_average"}` → `{expr}`
- Every feature payload accepts `signal_expr` (a formula), `signal_ref` (`"<id>@<version>"`) and `orthogonalize_against: [expr|library id]`. A formula overrides `signal`.
- Look-ahead guard: `result.meta.lookahead` = `{flagged:bool, reason?}` on every signal run.

## 2. Projects, persistence, ledger (agent P)
- Jobs and results persist in SQLite at `backend/data/research_v2.sqlite`, so `GET /jobs/{id}` works after a restart.
- `GET/POST /projects` `{name, description?}` → `{id,name,created_at}`. `GET /projects/{id}` → project plus runs, signals and preregistrations.
- Job payloads accept `project_id`; every run in a project is a *trial*.
- `GET /projects/{id}/ledger` → `{trials, distinct_signals, deflated_sharpe_hurdle, haircut_sharpe:{observed, haircut}, pbo?:number, entries:[{job_id, feature_id, signal, t_stat, sharpe?, created_at}]}`
- Holdouts and locks already exist. Expose `GET /projects/{id}/holdout` → `{sealed_after:date|null, unsealed:bool}` and `POST /projects/{id}/holdout` with `{sealed_after}` or `{unseal:true}`. While a holdout is sealed, jobs exclude data after the seal date.
- `POST /preregistrations` `{project_id, hypothesis, expected_sign, primary_test, signal}` → `{id, created_at}`. Results carry `meta.preregistered: bool`.
- `POST /share` `{job_id}` → `{token}`. `GET /share/{token}` → `{feature_id, result, created_at}`, read-only and unauthenticated.

## 3. Reports, protocol, data (agent R)
- `POST /report-card/jobs` `{payload}` runs Canonical, Robustness, Placebo, Regimes, Diagnostics, Decay and Factor zoo on one signal. Result:
  - `{grades:[{dimension, grade:"A".."F", score:0..100, summary, metric:{label,value}}], overall:{grade, score, verdict}, checklist:[{id, question, pass:bool|null, detail}], protocol:{name:"Novy-Marx & Velikov (2023)", steps:[{id,label,pass,detail}]}, explain:[str]}`
  - `explain` is plain-language sentences built from templates, no LLM.
- `POST /batch/jobs` `{signals:[expr|library id], payload}` → `{rows:[{signal, t_stat, p, p_adj_bhy, sharpe, ic, grade, survives:bool}], method:"BHY"}`
- `GET /report/{job_id}.tex` and `GET /report/{job_id}.pdf` give a referee-style report: abstract, tables, figures as data, robustness appendix, methods.
- `GET /universes` → `[{id, label, region, asset_type, count}]` over every universe in the parquet (4,300+ tickers). Payloads accept `universe_id`, `regions:[...]`, `asset_types:[...]`, `min_price`, `min_dollar_volume`, `min_listing_months`.
- Every result carries `meta.data_audit`: `{universe_size_by_month:[{month,n}], coverage_by_month:[{month,share}], missing_share, survivorship:"handled"|"not handled", pit_lag_days:number|null, adjustments:str[]}`.
- Costs: payloads accept `cost_model:{spread_bps, commission_bps, impact:"none"|"sqrt"}`. Results add `meta.costs:{breakeven_bps, net_sharpe, turnover, capacity_usd}`. `long_only:true` is supported.
- Walk-forward and CPCV: `POST /validation/jobs` `{payload, method:"walk_forward"|"cpcv", folds, embargo_days}` → `{folds:[{train, test, is_sharpe, oos_sharpe}], pbo, summary}`.
- `GET /literature/match` `?expr=` → `[{library_id, name, corr}]`, the nearest published anomalies by signal correlation.
- Input metadata in `GET /features`: every input gains `required:bool`, `depends_on:{field, values:[...]}|null`, `conflicts_with:[field]`, `unit`, `level:"quick"|"standard"|"expert"` and `citation?`.
- Feature merges for section B:
  - Diagnostics outputs are also returned by Canonical, in a "Model checks" section.
  - Regimes outputs are also returned by Robustness.
  - Synthetic control is design `"synthetic"` inside Causal designs.
  - Factor zoo outputs are also returned by Decay.
  - The old feature ids keep working.
