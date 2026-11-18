You are building the **backend of the Studio Build page** (strategy authoring and the Python strategy engine) in this repo. Go as far as your run allows, in the order below, without stopping to ask. Decide and keep going. Stop only if an action would destroy data or rewrite history.

The frontend is out of scope: another agent builds it against your API. Your job is an API so complete, fast and well tested that the frontend is only drawing.

## 1. Read first, in this order

1. `AGENTS.md`: repo rules. Smallest complete change, reuse before writing, verify before deleting, never touch `research_exports/`.
2. `docs/studio/plan/PYTHON_IDE.md`: the gap table (A1–A14 engine, B1–B13 IDE) and the order of work. **This is your main spec.**
3. `docs/studio/plan/CHECKLIST.md` § Build (B-1 … B-163): the only progress tracker. Items tagged `[PY]` or marked `backend done` / `partial` tell you what exists.
4. `docs/studio/plan/PAGES.md` § Build (spec §2) and its acceptance ids.
5. `docs/studio/standards/CODE_STANDARDS.md`: the quality gates every change must pass.
6. `docs/studio/plan/PLAN.md` §5 (backend architecture, engine, API) and `docs/studio/research/LEAN_PARITY.md` (indicator and fill definitions you must match).
7. The code you will extend, read in full before editing:
   - `backend/app/services/studio_v3/core/`: `spec.py`, `compile.py`, `formula.py`, `pycode.py` (AST checks), `pyrunner.py` (sandboxed child process), `engine.py`, `fills.py`, `backtest.py`, `store.py`, `templates.py`, `plain.py`, `limits.py`, `data.py`.
   - `backend/app/api/studio_v3.py`: all routes, under `/api/studio-v3/`.
   - `backend/tests/test_studio_v3_*.py`: existing fixtures and helpers (`client`, `store`, `data.panel`). Reuse them.

Read `REVIEW.md`, `COMPETITORS.md` and `FEATURES_PEAK.md` only when a decision needs the reason.

## 2. Scope: what to build, in order

Work the `PYTHON_IDE.md` order. Steps 1–8 below are the backend half of it, plus the open backend Build items in `CHECKLIST.md`.

1. **Runner output (A8, A9, A10, A11).**
   - Capture `print` and `ctx.log()` per bar as `{date, symbol, line, text}`, capped (for example 5,000 lines, then a truncation row).
   - `ctx.plot(name, value)` returns named series.
   - `warmup = n` means no orders before bar n.
   - `on_fill(ctx, fill)` receives symbol, side, quantity, price and date.
   - Runtime errors come back with file, line, column, the exception type and a short traceback limited to user frames.
2. **Portfolio API (A1, A2, A3, A5, A6, A13).**
   - `on_data(ctx)` sees every symbol in the bar.
   - Orders: `set_holdings(sym, w)`, `market_order(sym, qty)`, `limit_order`, `stop_order`, `liquidate()`.
   - Read-only portfolio state each bar: quantity, invested, unrealized P&L, cash, total value.
   - `ctx.history(fields, n)` returns numpy arrays. There is no look-ahead: index 0 is the current bar.
   - Schedule helpers: `is_month_start`, `is_week_start`, `every(n)`, and a `rebalance` hook.
   - **Orders go straight into the event engine and share the one fill model** (next open by default; worse-first when stop and target hit in the same bar).
   - Per-symbol `on_bar` stays as the simple mode and must keep giving identical trades (B-1 must still pass).
3. **Imports (A7).**
   - Allow-list: numpy, pandas, math, statistics, scipy.stats.
   - Enforce it twice: in the AST check and at import time through a restricted `__import__`.
   - Still refused: os, io, sys, socket, subprocess, importlib, ctypes, pickle, `open`, `eval`, `exec`, `__import__` strings, dunder escapes.
   - Keep the child process, rlimits, `-I` and the empty env. No network.
   - Write an escape test suite: at least 25 known sandbox breakouts, each refused.
4. **Language services for the editor (B6, B7, B5's go-to-definition).**
   - `POST /build/complete` returns completions: every `ctx` member, portfolio fields, indicator objects, numpy and pandas top-level names, and the user's own class members, with signatures and docs.
   - `POST /build/signature` gives signature help.
   - `POST /build/check` returns Problems for a debounced lint (target p95 under 150 ms for 300 lines): undefined names, unused variables, refused imports, look-ahead, unreachable orders. Each Problem has severity, file, line, column, end column, code and message.
   - `POST /build/definition` resolves local symbols.
   - Use `jedi` or `pyright` if it gives a clearly better result; adding a dependency is allowed (keep a fallback).
5. **Project files (B3).**
   - A strategy holds several files (`main.py`, `helpers.py` and so on) that import each other, and they are versioned together.
   - API: list, create, rename, delete and save a file.
   - The storage change stays backwards compatible: an existing single-code strategy reads as `main.py`.
   - Versions and diff work across files (B9; results side by side are already done).
6. **Template gallery (B10).** Eight starters, each compiling and producing at least one trade on the real data: trend, mean reversion, momentum rotation, pairs, volatility target, breakout, seasonality, ML-score.
7. **Debugger (B8).**
   - A bar stepper: run to a date and symbol, return the `self` attributes, the `ctx` snapshot and the orders that bar.
   - Step forward one bar by replaying deterministically in the runner, read-only.
   - Breakpoints by line, with an optional condition.
8. **Indicator objects (A4).**
   - `ctx.indicator("sma", sym, 50)` (and `self.sma(...)` style if cheap) with `ready`, `value` and `window`.
   - Definitions match LEAN exactly; add parity tests per `LEAN_PARITY.md`.
   - Then parameters declared in code show up in the Optimise grid automatically (A12).

Also close every other Build checklist item that is backend only or backend first. Examples:
- Condition true-rate and last-true date per rule (B-111, B-116).
- Always-true and always-false detector (B-108).
- Bars where a condition fired, without a backtest (B-109).
- Complexity meter: parameters, rules, degrees of freedom (B-117).
- Warm-up, data used and survivorship rows on the checks card (B-119).
- Missing exits and sizing modes (B-120, B-121).
- Any/All nesting in the spec (B-105).
- New condition kinds (B-106).
- Named variables and user functions in formulas (B-113).
- Monthly causal calls (B-114).

**B-163 (QuantConnect import):** do it after step 2 and step 8 land. Open a QuantConnect Python algorithm, keep the user's code, rewrite `QCAlgorithm` calls to Studio `ctx` calls with an AST transform, and return every line that wasn't converted, with a reason, before saving. A removed rules-only shim is in git at commit `4651300` (`core/imports.py`); reuse its call table, not its approach.

## 3. Performance budgets (measure them in tests)

- Compile: 20-row strategy under 100 ms (B-4, keep it).
- Lint, `/build/check`: p95 under 150 ms for 300 lines.
- Completion: p95 under 50 ms.
- Python backtest: 500 symbols × 2,500 bars under 20 s (A14). Vectorise formula precompute and keep per-bar Python work small. Use numba or numpy where the engine already does.
- Preview: server side under 300 ms after the last edit (B-5).

## 4. Hard rules

- **Real data only:** the parquets in `data/`. No mock numbers or invented results in API output. Test fixtures are fine inside tests. Do not fetch or rewrite any parquet.
- **No look-ahead, ever.** Every new data access path gets a test proving the future is refused, with the line and token named (B-2).
- **One fill model** shared by the vector and event engines. Python strategies must match trade for trade with the same rule written as blocks or a formula.
- **Sandbox first.** A feature that weakens the sandbox is not done. No Docker; it was deferred on purpose.
- **API shape:**
  - Typed pydantic request and response models.
  - Errors are `{detail}` with a 4xx code and a fix hint, matching the existing `Refusal(message, hints)` pattern.
  - Additive changes only to existing routes; the frontend is live.
  - Every new route goes in `app/api/studio_v3.py` next to its siblings.
- **Agent-friendly (AX):** every endpoint returns plain, self-describing JSON. Field names are full words, not abbreviations. Any job longer than about 2 s uses the existing `JobStore` with progress.
- **Smallest complete change:**
  - Reuse `compile`, `formula`, `fills`, `engine` and `store` before writing new modules.
  - No abstraction layers for one caller.
  - Remove code you replace.
  - Comment only the why.
- **Don't break other labs.**

## 5. How to work each step

1. Read the code it touches and list every caller (`rg`).
2. Write the tests first from the acceptance criterion: exact expected trades, logs, plots or problems on real data.
3. Implement.
4. Run the narrowest tests first, then all of Studio:
   `cd backend && PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_studio_v3_*.py`
   Then lint: `.venv/bin/ruff check app tests`. At the end of each step also run the full backend suite (`uv run pytest`).
5. Curl the new endpoints against the running server and paste one real response into the commit body.
6. Tick the item in `docs/studio/plan/CHECKLIST.md`, adding a short note in parentheses of what landed. Update the Build count and the All pages count in the Counts table.
7. Commit and push to `main`:
   - Stage only your own files with explicit paths.
   - Never use `--no-verify`. If the pre-commit hook fails on your code, fix the code.
   - The message says what changed and which ids it ticks.
8. Go straight to the next step.

## 6. Done means

- Each ticked item has a passing test that protects its acceptance criterion.
- All Studio tests, ruff and the full backend suite pass. Report the exact commands and counts.
- Performance budgets are measured and stated.
- No debug code, scratch files or dead paths.
- At the end, append a **Build backend** entry to `docs/studio/plan/PAGE_LOG.md` covering:
  - what shipped (by id);
  - the API list (method, path, one line each);
  - budgets measured;
  - what's still open and why;
  - known limits.

Write it plainly: no taglines, no marketing words.
