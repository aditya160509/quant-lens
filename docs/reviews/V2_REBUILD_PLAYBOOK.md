# V2 Module Rebuild Playbook

This is how Research V2 was rebuilt (commits fd8bb373 onward). Use it for Screener, Factors, ML, PCA, Portfolio and Volatility V2.

The reference implementation is `backend/app/services/research_v2/` plus `frontend/src/components/research-v2/`. Read its `DONE.md` before starting.

This is a framework, not a cage. If you find a better approach (a better library, a cleaner contract, a faster estimator), use it. Write down why in the module's `DONE.md`. The goals are fixed; the methods are not.

## Goals (fixed)

1. **Every number is real.** No proxies under a real estimator's name. No `Math.random()`. No demo data shown as a result. If the data cannot support something, the feature says so or the item is removed and listed under "Known limitations".
2. **No look-ahead.** Anything computed "as of" a past date uses only data available then: prices up to t, fundamentals 90 days after `reportDate`. Backtests reselect at every rebalance date.
3. **Fail loudly.** Unknown tickers give a 422 that lists them. Missing data shows up in the response and in the UI. No silent fallbacks.
4. **One contract.** The backend declares inputs and outputs. The frontend renders from that declaration and never re-declares it.
5. **Tested.** Golden numbers, look-ahead guards, API contract, frontend renderers.
6. **Uses proven open-source libraries** before hand-rolled math (statsmodels, linearmodels, arch, pyfixest, scipy, numba, and similar). New dependencies are allowed when they are the standard tool. List them in `requirements.txt`.

## Phase 1: Review (read-only)

- Read the spec (`docs/*.md` in the module), every core and feature file, the API router, the `main.py` mount, `frontend/src/lib/api.js` helpers, the pages and components, and the tests.
- Check the existing `docs/reviews/<MODULE>_V2_REVIEW.md`. Verify each claim against the code with line numbers. Add what it missed as an addendum.
- Classify every spec item as OK, WRONG (computes something else under the spec's name), PROXY, or MISSING.
- Specifically hunt for:
  - path or envelope mismatches between frontend and backend;
  - silent fallbacks;
  - look-ahead (latest fundamentals used for past dates, selection from current scores);
  - `fastmath`/NaN bugs;
  - proxies with real names;
  - `except Exception` that hides errors.

## Phase 2: Backend architecture

The target layout, mirroring Research V2:

| File | Role |
|---|---|
| `core/data_loader.py` | Strict symbol parsing (`UnknownSymbolsError`), point-in-time fundamentals, upload sandbox under `backend/data/<module>/uploads/` |
| `core/panel.py` (if cross-sectional) | One shared point-in-time panel dataclass that every feature builds on |
| `core/stats.py` | Statistical primitives with library-backed implementations |
| `core/estimators.py` | Shared estimators |
| `core/<feature>.py` | One module per feature. No 2,000-line `analytics.py` |
| `core/common.py` | JSON-safe response envelope (`records`, `response`) |
| `features/inputs.py` | Shared input builders |
| `features/feature_XX.py` | `INPUTS` (label, type, group, options, help, min/max, default), `OUTPUTS` (key, source, render hint, primary), `run()` |
| `registry.py` | Lazy: no feature imports at package import; serves `feature_manifest()` |

Rules:

- Delete a replaced file only after checking with `rg`, the import graph and the route registration. Record its fate in `DONE.md`.
- Never touch other V2 modules unless asked.

## Phase 3: API

`backend/app/api/<module>.py`, mounted in `main.py`:

- `GET /features`: the manifest.
- `GET /symbols`: search over the module's own universe.
- `POST /uploads?kind=`: validated, size-capped, sandboxed.
- `POST /feature/{id}/jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`: background jobs. Reuse the Studio `JobStore` with the module's own file under `backend/data/<module>/`, and store results per job.
- Map errors to status codes: `KeyError` → 404, `ValueError`/`TypeError`/`UnknownSymbolsError` → 422.

## Phase 4: Frontend

`frontend/src/components/<module>/`:

| File | Role |
|---|---|
| `api.js` | React Query hooks; a `use<Module>Job` that polls |
| `StudyForm.jsx` | Form generated from the manifest, with `toPayload` and `validate` |
| `renderers.jsx` | One component per render hint, plus `RENDERERS` and `RenderOutput`; shows "Not produced: why" for a missing output |
| `Workbench.jsx` | The page: form, job status, cards |
| `format.js`, `<module>.css` | Formatting and styles |

- Pages under `app/labs/<module>/` are thin wrappers.
- `layout.js` builds its nav from the manifest.
- Delete `customPagePrimitives.jsx`, hand-written `registry.js` and the demo fabricators.
- Visual polish is separate work (see `research_v2/WORK_LEFT.md`). Phase 4 is about correctness and the contract, not looks.

## Phase 5: Tests

- `backend/tests/test_<module>_math.py`: golden numbers on fixtures, plus look-ahead guards (data after t must not change results at t).
- `test_<module>_data_and_api.py`: strict tickers, sandbox, API status codes, and a render-hint contract test (every backend render hint exists in `renderers.jsx`).
- `test_<module>_features.py`: every feature returns every declared output on a small universe.
- `frontend/src/components/<module>/__tests__/`: payload coercion, validation, renderers, the missing-output message.

## Phase 6: Verify and document

Run:

```
cd backend && PYTHONPATH=. python3.11 -m pytest tests/test_<module>_*.py
cd frontend && npx jest src/components/<module> && npm run lint && npm run build
```

Then run one feature end to end in the browser and check that there are no console errors.

Write the module's `DONE.md`:

- architecture before and after;
- an old-file fate table;
- data rules;
- a feature × estimator table;
- known limitations (honest);
- the check commands.

Add a status note to the review file. Commit in logical steps, ending each message with the co-author line.

## Lessons from Research V2 (avoid repeating them)

- numba `fastmath=True` breaks `np.isfinite`.
- Monthly factor returns must be compounded, not summed.
- Time-displacement placebos must displace by at least lookback + holding period, or they overlap with the real signal.
- A pooled Chow test needs within-date demeaning.
- Cluster-robust Wald tests over-reject with few clusters; fall back and say so.
- Suppress noisy library stdout (rdrobust) and pin random seeds.
- Commit before `git rm` on untracked files.
- Python 3.11 is required; the system `python3` is 3.9.
