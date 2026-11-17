# Code standards: the review checklist

Check every change against this file before it is committed. Each line is a yes/no question. A "no" is a bug, or it is written into `DECISIONS.md` with the reason.

Studio paths: `backend/app/services/studio_v3/{core,features}`, `backend/app/api/studio_v3.py`, `backend/tests/test_studio_v3_*.py`, `frontend/src/modules/studio/`.

## 0. Gates (run these; all must pass)

```bash
cd backend && .venv/bin/ruff check -q app/services/studio_v3 app/api/studio_v3.py tests/test_studio_v3_*.py
cd backend && PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_studio_v3_*.py
cd frontend && npx tsc --noEmit -p . && npx oxlint src/modules/studio
gitleaks git --redact .   # before making anything public
```

- [ ] Pre-commit hook passed without `--no-verify`.
- [ ] The page was opened in the browser at 1440 px after the change, with a fresh run, and the console has no errors.

## 1. Quant correctness (the reason this product exists)

- [ ] **No look-ahead.** Every signal uses data up to the close of bar t and acts at bar t+1 (or the same close only when the user picked it). Any rolling estimate (weights, regimes, z-scores) uses only past bars. Shifts are explicit: `out[1:] = x[:-1]`.
- [ ] **No look-ahead in parameter choice.** Anything "best" (cell, weight, threshold) chosen on the same data it is scored on is labelled in-sample, or is re-chosen walk-forward.
- [ ] **Hold-out stays sealed.** No code path returns hold-out bars unless `open_holdout` was called and logged. Agents cannot bypass the look budget.
- [ ] **Trials are counted.** Every backtest, sweep cell and validation variant a user or agent triggers lands in the trial ledger; effective trials feed the deflated Sharpe.
- [ ] **Engine parity.** Any change to fills, sizing, costs or exits runs on both engines (vector and event) and `both()` in `test_studio_v3_engine.py` checks they match trade for trade.
- [ ] **Fill rules are worst case.** Gaps fill at the open; stop before target inside one bar; costs on both sides; borrow on shorts; delisted names settle at the last close (less the haircut).
- [ ] **Survivorship is stated.** Universes chosen by today's liquidity say so in the limits list.
- [ ] **Annualisation is right.** Daily Sharpe × √252, returns compounded, not summed; drawdown from the running peak of equity, not of returns.
- [ ] **NaN is handled on purpose.** No silent `fillna(0)` on prices; a name with no bar is not traded; `np.nan*` functions where gaps are expected; empty arrays guarded before `argmax`, `min`, `max`.
- [ ] **Edge cases tested.** Zero trades, one name, a name that delists mid-run, a flat series (std 0), fewer than 20 trades (Kelly refuses), fewer settings than a test needs (skipped with a reason, not crashed).
- [ ] **Numbers are reproducible.** Same spec, settings and data give the same `result_hash`. Randomness takes `settings.seed`.
- [ ] **Every number shown comes from a real run.** No placeholder, sample or invented figure in the UI or docs.

## 2. Data honesty

- [ ] The run's limits list prints every caveat that applies: data range, coverage, universe bias, delisted share, fill model, costs, hold-out, adjustment, dividends.
- [ ] A feature that the data cannot support is removed or refused, not shown with a guess (see `DECISIONS.md`).
- [ ] Freshness is shown; nothing labelled "today" runs on stale bars without saying the last date.
- [ ] Data version is part of the run hash.

## 3. Correctness of code (general)

- [ ] The root cause is fixed once in shared code; every caller was grepped (`rg`, codebase-memory) before editing.
- [ ] No dead code, unused imports, commented-out code, debug prints, TODO without a checklist line.
- [ ] No two implementations of the same behaviour.
- [ ] Types are honest: no `any`/`as unknown as` in TypeScript unless the API shape is typed right next to it; Python functions have annotations.
- [ ] Errors are not swallowed. `except` names the exception; user-facing refusals use `Refusal(reason, causes)`.
- [ ] Functions do one thing; a reader understands each line without a comment. Comments say why, not what.
- [ ] Constants are named (`MAX_MEMBERS`, `FEW_TRADES`), not repeated literals.

## 4. Security

- [ ] User input is validated at the API boundary (pydantic models with `extra="forbid"`, numeric bounds).
- [ ] Formulas and custom objectives go through the AST allow-list evaluators; nothing reaches `eval`/`exec`.
- [ ] Python strategies run only in the child process (`-I`, empty env, rlimits, safe builtins, AST screen); no new builtin is allowed without a test that it cannot read files, the network or the environment.
- [ ] No secret in code, tests or docs. Test fixtures use obviously fake values. `.env` files stay ignored.
- [ ] Agent tools cannot do what needs a human (freeze, open the hold-out beyond budget, send money or messages).
- [ ] SQL uses parameters, never string formatting. File paths from users are refused or sandboxed.
- [ ] No user data in URLs or logs.

## 5. Performance

- [ ] Hot loops are vectorised (numpy) or compiled (numba `njit(cache=True)`); no Python loop over bars × symbols in the vector engine.
- [ ] Data loads are cached by data version (`lru_cache` keyed on the version), not re-read per request.
- [ ] Long jobs run through `_execute` with progress, never block the request thread.
- [ ] Payloads are thinned for charts (≤ ~2,000 points per series).
- [ ] Quick validation profile stays under 10 s on the default universe.

## 6. API and storage

- [ ] Public API, schema, storage or wire format changes are backwards compatible (old saved runs still load) or written in `DECISIONS.md`.
- [ ] Every new output is listed in the feature's `OUTPUTS` and has a view in `studioLab.ts`; keys do not clash between `tables` and `charts`.
- [ ] Agent (MCP) tools return the same numbers the page shows.

## 7. Tests

- [ ] New non-trivial logic has one small test that would fail if the logic broke (not a snapshot of whatever it returns).
- [ ] Tests extend the closest existing file; no new test infrastructure for one change.
- [ ] Tests use fixture data, not the live parquet, unless the test is about the live data.
- [ ] Each quant test states the acceptance rule in its name or a one-line comment (e.g. `# no look-ahead: equal weight until a year of history`).

## 8. UI and UX (no slop)

- [ ] No taglines, helper text, secondary labels or repeated headlines. A number or a chart says it; one line of caption at most.
- [ ] No decorative coloured backgrounds, edge accents, gradients, glows or icons in tinted squares. Colour encodes data or status only (`--up`, `--down`, `--warn`).
- [ ] Each chart answers one question and is the right form for it (distribution → histogram, two measures → scatter, over time → line, matrix → heatmap).
- [ ] Every view has empty, loading, error and skipped states; skipped says why in plain words.
- [ ] Nothing on the page repeats another element (hero line vs headline, card vs table).
- [ ] Numbers are formatted with units and sensible precision; tabular figures align.
- [ ] Works at 390 px wide without horizontal scroll (phase 8 for pages not yet done).
- [ ] Copy is plain English, verb first on buttons, no jargon without the number next to it.

## 9. Accessibility

- [ ] Every input has a label; icon buttons have `aria-label`.
- [ ] Keyboard reaches and operates every control; focus is visible; Esc closes overlays.
- [ ] Charts have an accessible name; colour is never the only signal (pass/fail also has text).
- [ ] oxlint a11y rules pass (the hook rejects them).

## 10. Dependencies and licences

- [ ] A new dependency earns its place (no package for a few lines) and its licence allows use here (no AGPL in the app; check `OPEN_SOURCE.md`).
- [ ] Versions are pinned in the lockfile.

## 11. Git and docs

- [ ] Only your own files are staged; unrelated user changes stay out.
- [ ] One verified chunk per commit, message says what changed for the user.
- [ ] `CHECKLIST.md` ticked; `DECISIONS.md` updated for any removal, limit or trade-off.
- [ ] `research_exports/` is never cleaned.

## 12. Before calling it done

- [ ] The requested behaviour works in the browser with real data.
- [ ] Gates in §0 pass, with the commands and results written in the report.
- [ ] Assumptions, limits and anything not verified are stated plainly.
