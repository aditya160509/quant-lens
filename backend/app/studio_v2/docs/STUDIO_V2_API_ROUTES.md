# Studio v2 — Backend API Routes & Implementation Plan

## Backend completion checklist

- [x] F1.10 executable strategy template library, retrieval, and durable forking
- [x] F1.11 multi-strategy portfolio composition and combined execution
- [x] F1.12 portable standalone strategy ZIP export
- [x] F1.13 token-gated collaborative WebSocket sessions
- [x] F1.14 isolated compute jobs, live status, queueing, and process termination
- [x] F1.15 persistent snippet CRUD and tag filtering
- [x] F2.9 portfolio-level backtesting and complete result persistence
- [x] F2.10 Brinson-Fachler sector attribution and factor regression
- [x] F2.11 historical execution/slippage audit with disclosed proxy fallback
- [x] F2.12 FIFO tax lots, holding-period tax rates, wash sales, and post-tax equity
- [x] F2.13 named scenario replay and persistent results
- [x] F2.14 multi-run strategy comparison
- [x] F3.10 cross-source robustness testing
- [x] F3.11 signed, hash-chained look-ahead audit trails
- [x] F3.12 factorial parameter-interaction diagnostics
- [x] F3.13 persistent adversarial stress runs
- [x] F4.12 composite factor construction
- [x] F4.13 turnover-decay and cost-aware rebalance diagnostics
- [x] F4.14 durable factor version governance
- [x] F5.7 multi-objective Pareto frontier analysis
- [x] F5.8 trial/parameter ensembles
- [x] F5.9 purged and embargoed optimizer cross-validation
- [x] F6.11 normalized multi-asset-class metadata
- [x] F6.12 persistent corporate-event calendar
- [x] F6.13 explicit and inferred synthetic-range flagging
- [x] Page 7 portfolio VaR/CVaR, correlation, concentration, limits, breaches, and alerts
- [x] Cross-cutting persistent research journal
- [x] Studio V2 router mounted in the application under `/api/v2`
- [x] Route-contract, math-invariant, persistence, import, and OpenAPI verification

**Purpose:** Documents every new feature, the backend files needed, and exactly which API routes to add — all following the existing `router.py` patterns (direct handler methods, `lazy_info` dispatch, or new lazy dispatchers).

---

## F1.10 — Strategy Template Library

### What It Is

A gallery of pre-built starter strategies covering the canonical families: cross-sectional momentum, time-series momentum, mean-reversion (pairs and single-name), statistical arbitrage, volatility carry, and simple factor-tilt. Each template is a fully working, backtestable strategy file with inline comments explaining the logic, not pseudocode. Selecting one forks it directly into a new Algorithm Lab session, pre-wired to the platform's data accessors and config schema. Templates are tagged by complexity (beginner/intermediate/advanced) and by required universe type.

### Why It Exists

Bloomberg BQuant Enterprise charges $32,000/year/seat for a Python analytics sandbox with no starter templates — every user starts from a blank editor. QuantConnect has a small library but templates are read-only and cannot be forked into editable sessions. This feature eliminates the blank-page problem: a researcher can have a working, backtestable strategy in under 60 seconds, choosing from proven templates organized by strategy family and complexity level. Templates are also educational — each one is heavily commented, serving as both a starting point and a learning resource for newer researchers.

### What It Does

1. Lists all available templates with metadata (name, family, complexity level, universe type, one-line description)
2. Returns full source code for a selected template
3. Forks a template into a new Algorithm Lab session — copies the source, creates a new session with the kernel initialized, and returns the session ID so the frontend navigates directly to the editor

### How Researcher Uses It

A researcher exploring mean-reversion strategies clicks "Strategy Templates" → filters by "Mean Reversion" → sees 3 options (pairs, single-name, statistical arbitrage) → clicks "Pairs Mean Reversion" → hits "Fork to Editor" → lands in Algorithm Lab with the complete template code loaded, data accessors pre-wired, and config schema populated.

### New Files to Create

```
backend/app/studio_v2/algorithm_lab/templates.py
  - Template class: id, name, family, complexity, universe_type, description, source_path
  - TemplateRepository class:
    - list_templates(family?, complexity?) → Template[]
    - get_template(id) → Template with source code
    - fork_template(id, session_name?) → creates new KernelGateway session, copies source
  - Template metadata stored as JSON index + .py files in data/templates/

backend/app/studio_v2/data/templates/
  - cross_sectional_momentum.py
  - time_series_momentum.py
  - pairs_mean_reversion.py
  - single_name_mean_reversion.py
  - statistical_arbitrage.py
  - volatility_carry.py
  - factor_tilt.py
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import TemplateRepository at top
  - Store self.templates = TemplateRepository() in __init__
  - Add 3 routes to the routes dict:
    "/api/v2/algorithm-lab/templates": (self.list_templates, "GET")
    "/api/v2/algorithm-lab/templates/{id}": (self.get_template, "GET")
    "/api/v2/algorithm-lab/templates/{id}/fork": (self.fork_template, "POST")
  - Add 3 handler methods on the Router class
```

### Integration Pattern

All 3 routes follow the **direct handler** pattern, same as `execute_code`, `variables`, `lint`. They are added to the `routes` dict in `_register_routes()`, with handler methods defined on the Router class.

### API Routes

```
GET /api/v2/algorithm-lab/templates
  Query: family?, complexity?
  Response: [
    {
      "id": "cross_sectional_momentum",
      "name": "Cross-Sectional Momentum",
      "family": "momentum",
      "complexity": "intermediate",
      "universe_type": "equity",
      "description": "Ranks stocks by trailing 12-month return, longs top decile, shorts bottom decile. Includes sector-neutral version."
    },
    ...
  ]

GET /api/v2/algorithm-lab/templates/{id}
  Response: {
    "id": "cross_sectional_momentum",
    "name": "Cross-Sectional Momentum",
    "source_code": "# Cross-Sectional Momentum Strategy\n...",
    "default_config": { "lookback": 252, "holding_period": 21, "top_pct": 0.1, "bottom_pct": 0.1 },
    "metadata": { ... }
  }

POST /api/v2/algorithm-lab/templates/{id}/fork
  Body: { "session_name": "My Momentum Experiment" }
  Response: {
    "session_id": "sess_abc123",
    "file_path": "/strategies/my_momentum_experiment.py",
    "source_code": "# Cross-Sectional Momentum Strategy\n...",
    "editor_state": { "language": "python", "content": "..." }
  }
```

---

## F1.11 — Multi-Strategy Portfolio Composition View

### What It Is

A workspace where a researcher selects 2–10 strategies already built in Algorithm Lab and combines them into a single portfolio construct with configurable weighting — equal-weight, risk-parity (weights inversely proportional to each strategy's return variance), or a custom Python allocator function that the researcher writes directly. The combined kernel execution is the critical innovation: instead of aggregating outputs after the fact, each sub-strategy's signals are exposed as named variables in the combined kernel's namespace, so the researcher can write cross-strategy allocation logic that references individual strategy signals directly as Python variables. This means the allocation logic runs in the same kernel process as the strategies themselves — no serialization, no IPC, no translation layer.

### Why It Exists

No existing quant platform — including QuantConnect, BQuant, or any retail tool — allows a researcher to compose multiple strategies into a single portfolio and inspect their combined behavior before running a portfolio-level backtest. The standard workflow is: build Strategy A, backtest it → build Strategy B, backtest it → manually combine P&Ls in a spreadsheet. This feature makes the composition explicit, inspectable, and testable within the same interactive environment, and it directly feeds the portfolio-level backtest (F2.9) and the Risk Management page (Page 7).

### What It Does

1. Creates a portfolio composition from a list of strategy IDs with a weight scheme
2. Each strategy's signal variables are namespaced (e.g., `strat_0_positions`, `strat_1_positions`, `strat_2_signals`)
3. The allocator function (built-in or custom) reads these named variables and produces combined portfolio weights
4. Executing the combined kernel runs all strategies + allocator in one pass, returning both individual and combined outputs

### How Researcher Uses It

A researcher has 3 strategies: momentum, mean-reversion, and volatility carry. She selects all 3, chooses "risk-parity" weighting, and clicks "Execute Combined." The combined kernel runs all 3 strategies against the same data, exposes `momentum_positions`, `mean_reversion_positions`, `vol_carry_signals` as variables, applies risk-parity weights, and returns the combined portfolio weights + each strategy's individual outputs side-by-side. She can then click "Push to Portfolio Backtest" (F2.9) to run the full simulation.

### New Files to Create

```
backend/app/studio_v2/algorithm_lab/portfolio_composer.py
  - Composition schema: id, strategy_ids, weight_scheme, namepace_map
  - PortfolioComposer class:
    - create(strategy_ids, weight_scheme, name) → composition_id
    - get(id) → Composition with full details
    - execute(id) → runs each strategy's code in isolated sub-namespaces,
                     applies allocator, returns combined outputs
    - _equal_weight(returns_matrix) → weights
    - _risk_parity(returns_matrix) → inverse-variance weights
    - _custom_allocator(python_code, strategy_vars) → weights from user function
```

### Files to Modify

```
backend/app/studio_v2/algorithm_lab/kernel.py
  - Add execute_multi(namespace_map: dict, allocator_code: str) method
  - Each strategy runs in isolated sub-namespace within the same kernel
  - Allocator code has access to all sub-namespace variables via a composite namespace
  - Sub-namespaces are prefixed (e.g., "strat_0", "strat_1") to avoid collisions

backend/app/studio_v2/router.py
  - Import PortfolioComposer at top
  - Store self.composer = PortfolioComposer() in __init__
  - Add 3 routes to the routes dict:
    "/api/v2/algorithm-lab/compose": (self.create_composition, "POST")
    "/api/v2/algorithm-lab/compose/{id}": (self.get_composition, "GET")
    "/api/v2/algorithm-lab/compose/{id}/execute": (self.execute_composition, "POST")
  - Add 3 handler methods
```

### Integration Pattern

Direct handler methods — same pattern as `execute_code`, `variables`, `push_to_backtest`. These routes have specific orchestration logic (multi-strategy namespace, weight computation) that doesn't fit the lazy dispatch pattern.

### API Routes

```
POST /api/v2/algorithm-lab/compose
  Body: {
    "strategy_ids": ["strat_abc", "strat_def", "strat_ghi"],
    "weights": "risk_parity",
    "portfolio_name": "Q4 Momentum + MeanRev + VolCarry"
  }
  Response: {
    "composition_id": "comp_123",
    "strategies": [
      { "id": "strat_abc", "name": "Cross-Sectional Momentum" },
      { "id": "strat_def", "name": "Pairs Mean Reversion" },
      { "id": "strat_ghi", "name": "Volatility Carry" }
    ],
    "weight_scheme": "risk_parity",
    "namespace_keys": ["strat_0_positions", "strat_1_positions", "strat_2_signals"]
  }

GET /api/v2/algorithm-lab/compose/{id}
  Response: full composition with current state, last execution time, etc.

POST /api/v2/algorithm-lab/compose/{id}/execute
  Body: {}
  Response: {
    "individual": {
      "strat_0": { "positions": [...], "signals": [...], "variables": {...} },
      "strat_1": { "positions": [...], "signals": [...], "variables": {...} },
      "strat_2": { "signals": [...], "variables": {...} }
    },
    "combined": {
      "weights": { "strat_0": 0.45, "strat_1": 0.30, "strat_2": 0.25 },
      "allocator_output": "..."
    }
  }
```

---

## F1.12 — Notebook-to-Production Export

### What It Is

A one-click export that strips all platform-specific dependencies (kernel comms, autocomplete provider, dependency graph hooks) from a strategy file and outputs a clean, standalone Python module containing only the pure `generate_signals()` function and its explicit imports (pandas, numpy, and nothing else). Includes a minimal `requirements.txt` (pandas, numpy) and a README describing the expected input schema. This is the artifact a researcher hands to an execution engineer or uploads to an external execution system.

### Why It Exists

The single most common complaint across every quant platform is vendor lock-in: "My strategy works on Platform X, but I can't run it anywhere else." QuantConnect users must use LEAN's API. BQuant strategies depend on Bloomberg data bindings. VectorBT strategies reference VectorBT-specific objects. This feature makes every strategy on the platform portable. The export is specifically designed to be the handoff artifact a researcher gives to an execution engineer who will implement it in whatever production system the fund uses.

### What It Does

1. Accepts a strategy ID
2. Parses the strategy source code into an AST
3. Identifies and removes platform-specific imports and function calls
4. Injects standalone equivalents where needed
5. Generates a clean Python file containing only: `import pandas as pd`, `import numpy as np`, and the pure signal logic
6. Wraps everything in a ZIP with `requirements.txt` and `README.md`

### How Researcher Uses It

A researcher has perfected a momentum strategy in Algorithm Lab. She clicks "Export → Production Module." The platform strips out all `from quant360 import data_loader`, `open_kernel()`, `ctx.get_variable()` calls and returns a ZIP. She emails it to the execution team, who reads the README, installs pandas + numpy, and calls `generate_signals(ohlcv_df)` from their production system.

### New Files to Create

None — the export logic is a self-contained utility that can live in the router handler.

### Files to Modify

```
backend/app/studio_v2/router.py
  - Add to routes dict:
    "/api/v2/algorithm-lab/export/{strategy_id}": (self.export_standalone, "POST")
  - Add export_standalone handler method:
    - Read strategy file from kernel source
    - Parse AST, strip platform dependencies
    - Generate requirements.txt, README.md
    - Return StreamingResponse with application/zip
```

### Integration Pattern

Direct handler — the export logic is specific enough to warrant its own method.

### API Routes

```
POST /api/v2/algorithm-lab/export/{strategy_id}
  Body: {}
  Response: application/zip containing:
    - strategy_module.py
    - requirements.txt
    - README.md
```

---

## F1.13 — Collaborative Kernel Sessions

### What It Is

A mode where a second user can join an active kernel session as a read-only or co-editing observer. The joining user sees the same editor state, variable inspector, and live chart panel in real time, synchronized via WebSocket. Cursor position and active cell are visible per participant, with name tags so each person knows who is editing what. This is designed for research pair programming, mentor review sessions, and handoffs where one researcher needs to walk another through a complex strategy without resorting to screen-sharing tools outside the platform.

### Why It Exists

Quant research is rarely done in isolation. At every fund, senior researchers review juniors' code, teams pair on difficult signals, and departing researchers hand off their work to successors. Current tools require screen-sharing (Zoom, Slack huddles) or exporting and re-importing code — both are friction-heavy and lose the live kernel state. WebSocket-based collaborative editing is standard in software engineering (VS Code Live Share, Google Docs) but absent from every quant platform. This feature brings that standard to quant research.

### What It Does

1. A primary user has an active kernel session
2. They invite a second user via the API, specifying read-only or edit role
3. The second user connects via WebSocket and immediately receives the full session state: editor content, cursor positions per participant, variable inspector data, chart state
4. Any change (code edit, cell execution, variable update, chart render) is broadcast to all connected participants
5. Cursor positions are synced in real time with user name tags
6. Read-only participants can view everything but cannot execute code or edit files

### How Researcher Uses It

A senior researcher wants to review a junior's new factor. She opens the strategy, clicks "Invite Collaborator," enters the junior's username, and sets role to "edit." The junior connects and sees the same editor with the senior's cursor visible. They discuss the code in real time. The junior makes edits that the senior can see live. When they're done, the senior clicks "End Collaboration" and the session reverts to single-user.

### New Files to Create

```
backend/app/studio_v2/algorithm_lab/collaboration.py
  - CollaboratorSession class:
    - create(session_id, primary_user_id) → collab session
    - invite(session_id, user_id, role) → invite token
    - join(session_id, invite_token, websocket) → connected
    - leave(session_id, user_id) → disconnect
    - get_participants(session_id) → [{ user_id, role, connected_since, cursor_position }]
  - WebSocket message types:
    - cursor_position: { user_id, position, line, column }
    - cell_execution: { user_id, cell_id, code }
    - variable_update: { snapshot }
    - chart_snapshot: { chart_data }
    - participant_joined: { user_id, name, role }
    - participant_left: { user_id }
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import CollaboratorSession at top
  - Store self.collab = CollaboratorSession() in __init__
  - Add to routes dict:
    "/api/v2/algorithm-lab/session/{session_id}/collaborate": (self.collab_ws, "WS")
  - Add to routes dict:
    "/api/v2/algorithm-lab/session/{session_id}/invite": (self.invite_collaborator, "POST")
    "/api/v2/algorithm-lab/session/{session_id}/participants": (self.get_participants, "GET")
  - Add 3 handler methods
```

### Integration Pattern

WebSocket endpoint + 2 REST endpoints — all direct handlers.

### API Routes

```
WS /api/v2/algorithm-lab/session/{session_id}/collaborate
  WebSocket channel
  Inbound message types:
    { "type": "cursor_update", "position": { "cell_id": "cell-1", "line": 42, "column": 15 } }
    { "type": "cell_executed", "cell_id": "cell-1" }
  Outbound message types:
    { "type": "participant_joined", "user_id": "usr_456", "name": "Alice", "role": "edit" }
    { "type": "cursor_update", "user_id": "usr_456", "name": "Alice", "position": {...} }
    { "type": "variable_snapshot", "variables": {...} }
    { "type": "chart_snapshot", "chart_data": {...} }

POST /api/v2/algorithm-lab/session/{session_id}/invite
  Body: { "user_id": "usr_456", "role": "edit" }
  Response: { "invite_token": "tok_xyz123", "expires_at": "2026-08-01T12:00:00Z" }

GET /api/v2/algorithm-lab/session/{session_id}/participants
  Response: [
    { "user_id": "usr_123", "name": "Bob", "role": "owner", "connected_since": "...", "cursor_position": {...} },
    { "user_id": "usr_456", "name": "Alice", "role": "edit", "connected_since": "...", "cursor_position": {...} }
  ]
```

---

## F1.14 — Compute Budget Guardrail Panel

### What It Is

A persistent status indicator showing the current session's active compute load — how many cells are running, what Monte Carlo or optimizer jobs are queued — with a manual kill switch per running process. Any cell execution exceeding a configurable wall-clock threshold (default 60 seconds) surfaces a "still running — kill?" prompt rather than silently blocking the session indefinitely. Without this, a long-running cell (e.g., a 10-minute Monte Carlo simulation) holds the session hostage — the researcher cannot execute other cells, cannot inspect variables, and has no way to cancel except closing the browser tab.

### Why It Exists

Quant researchers frequently run expensive computations (Monte Carlo, grid searches) that take minutes or hours. In the current jupyter-notebook model, a long-running cell blocks the entire kernel with no visibility into what's running and no kill button. This feature is the solution: it makes every running process visible, killable, and timed.

### What It Does

1. Registers every cell execution as a tracked job when it starts
2. Reports which jobs are running, how long they've been running, and what's queued
3. Kills a specific job by ID (SIGTERM first, then SIGKILL after 3 seconds)
4. Kills all running jobs at once
5. Enforces a configurable wall-clock timeout — when a job exceeds it, the frontend prompts the user before allowing it to continue

### How Researcher Uses It

A researcher accidentally starts a 10,000-simulation Monte Carlo run instead of 1,000. After 30 seconds, the Compute Guardrail shows the job running for 30 seconds. The researcher clicks "Kill" — the compute_budget.py sends SIGTERM to the subprocess, the job stops, and the researcher corrects the parameter.

### New Files to Create

```
backend/app/studio_v2/algorithm_lab/compute_budget.py
  - Job schema: id, type, cell_id, started_at, elapsed_seconds, status
  - ComputeBudget class:
    - start_job(session_id, job_id, type, cell_id)
    - complete_job(session_id, job_id)
    - get_status(session_id) → { running: Job[], queued: Job[], threshold_seconds }
    - kill_job(session_id, job_id) → sends SIGTERM → 3s grace → SIGKILL
    - kill_all(session_id) → kill every running job
    - set_threshold(seconds) → update timeout
```

### Files to Modify

```
backend/app/studio_v2/algorithm_lab/kernel.py
  - Integrate ComputeBudget lifecycle:
    - Before cell execution: compute_budget.start_job(...)
    - After cell execution: compute_budget.complete_job(...)
    - Before execution: check if previous job exceeds threshold, prompt via flag

backend/app/studio_v2/router.py
  - Import ComputeBudget
  - Store self.budget = ComputeBudget() in __init__
  - Add to routes dict:
    "/api/v2/algorithm-lab/session/{session_id}/compute-status": (self.compute_status, "GET")
    "/api/v2/algorithm-lab/session/{session_id}/kill/{job_id}": (self.kill_job, "POST")
    "/api/v2/algorithm-lab/session/{session_id}/kill-all": (self.kill_all_jobs, "POST")
  - Add 3 handler methods
```

### Integration Pattern

Direct handlers — each route has unique orchestration logic.

### API Routes

```
GET /api/v2/algorithm-lab/session/{session_id}/compute-status
  Response: {
    "running": [
      { "job_id": "job_001", "type": "cell_execution", "cell_id": "cell-3", "elapsed_seconds": 42.5, "started_at": "..." },
      { "job_id": "job_002", "type": "monte_carlo", "cell_id": "cell-5", "elapsed_seconds": 12.1, "started_at": "..." }
    ],
    "queued": [
      { "job_id": "job_003", "type": "cell_execution", "cell_id": "cell-6", "position": 1 }
    ],
    "threshold_seconds": 60
  }

POST /api/v2/algorithm-lab/session/{session_id}/kill/{job_id}
  Response: { "killed": true, "job_id": "job_001", "signal": "SIGTERM" }

POST /api/v2/algorithm-lab/session/{session_id}/kill-all
  Response: { "killed": 2, "job_ids": ["job_001", "job_002"] }
```

---

## F1.15 — Snippet/Macro Library

### What It Is

A lightweight, separate-from-version-control library of reusable code fragments — a rolling z-score helper, a standard cost-model boilerplate block, a common plotting call — insertable via a command palette or autocomplete trigger in the Monaco editor. Snippets differ from version-controlled files in an important way: they are meant to be copied, pasted, and modified into the current strategy, not tracked as artifacts. This is a personal toolkit, not a source control system.

### Why It Exists

Every quant researcher has a personal library of utility functions and boilerplate blocks they reuse across strategies. Without this feature, they maintain these as loose files, snippets in a notes app, or muscle memory. This makes that personal toolkit available directly in the editor, insertable with a few keystrokes, with no file management overhead.

### What It Does

1. Lists all saved snippets, optionally filtered by tag
2. Creates a new snippet with name, code, language, and tags
3. Updates an existing snippet's name, code, or tags
4. Deletes a snippet

### How Researcher Uses It

A researcher has a snippet called "Rolling Z-Score" that she uses in every strategy. In the editor, she opens the snippet library, searches "z-score," clicks insert, and the snippet code appears at the cursor position.

### New Files to Create

```
backend/app/studio_v2/algorithm_lab/snippets.py
  - Snippet schema: id, name, code, language, tags, created_at, updated_at
  - SnippetRepository class:
    - list(tag?) → Snippet[]
    - get(id) → Snippet
    - create(name, code, language, tags) → Snippet
    - update(id, name?, code?, tags?) → Snippet
    - delete(id) → void
  - Backend storage: JSON file or simple SQLite
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import SnippetRepository
  - Store self.snippets = SnippetRepository() in __init__
  - Add 4 routes to the routes dict:
    "/api/v2/algorithm-lab/snippets": (self.list_snippets, "GET")
    "/api/v2/algorithm-lab/snippets": (self.create_snippet, "POST")  — same path, different method
    "/api/v2/algorithm-lab/snippets/{id}": (self.update_snippet, "PUT")
    "/api/v2/algorithm-lab/snippets/{id}": (self.delete_snippet, "DELETE")
  - Add 4 handler methods
```

### Integration Pattern

Direct handlers — simple CRUD, no lazy dispatch needed.

### API Routes

```
GET /api/v2/algorithm-lab/snippets
  Query: tag?
  Response: [
    { "id": "snp_001", "name": "Rolling Z-Score", "code": "def rolling_zscore(series, window):\n    ...", "language": "python", "tags": ["statistics", "helper"], "created_at": "..." },
    ...
  ]

POST /api/v2/algorithm-lab/snippets
  Body: { "name": "Adjusted Costs", "code": "def adjusted_cost_model(...):\n    ...", "language": "python", "tags": ["costs", "boilerplate"] }
  Response: { "id": "snp_002", ... }

PUT /api/v2/algorithm-lab/snippets/{id}
  Body: { "name": "Updated Name", "code": "..." }
  Response: { "id": "snp_002", ... }

DELETE /api/v2/algorithm-lab/snippets/{id}
  Response: { "deleted": true, "id": "snp_002" }
```

---

## F2.9 — Multi-Strategy / Portfolio-Level Backtest

### What It Is

Runs the combined portfolio construct (from F1.11) through the event-driven engine as a single simulation. The engine runs each strategy independently against the same market data, collects their daily returns, applies the portfolio weights, and produces a combined equity curve, combined Sharpe/Sortino/drawdown, and — critically — a pairwise correlation matrix between the constituent strategies' daily returns. Any pair with correlation above a configurable threshold (default 0.7) is flagged as redundant diversification: the portfolio is paying for two strategies that behave identically.

### Why It Exists

Every existing backtesting platform tests one strategy at a time. If a researcher wants to test a portfolio of strategies, they must run them individually, export the P&Ls, and combine them in a spreadsheet. This does the combination natively, with the same event-driven rigor applied to each constituent, and explicitly flags when diversification is illusory (high correlation between strategies).

### What It Does

1. Accepts a composition ID (from F1.11) and a backtest configuration
2. Runs the event-driven engine for each constituent strategy independently
3. Collects each strategy's daily return series
4. Applies the composition's weight scheme to produce a combined daily return series
5. Computes combined portfolio metrics: Sharpe, Sortino, max drawdown, Calmar
6. Computes pairwise correlation matrix across all constituent daily return series
7. Flags any pair exceeding the correlation threshold
8. Returns the combined result + per-strategy breakdown + correlation matrix + flags

### New Files to Create

```
backend/app/studio_v2/backtest/portfolio_engine.py
  - PortfolioRunConfig schema: composition_id, config (date_range, benchmark, cost_model, ...)
  - PortfolioResult schema: combined_metrics, per_strategy_metrics, correlation_matrix, flags
  - PortfolioEngine class:
    - run(composition_id, config) → PortfolioResult
    - Loads composition from PortfolioComposer
    - For each strategy: load source, run EventDrivenEngine, collect daily returns
    - Combine returns using composition's weight scheme
    - Compute combined metrics
    - Compute pairwise correlation matrix (via numpy.corrcoef)
    - Flag redundant pairs (threshold default 0.7)
```

### Files to Modify

```
backend/app/studio_v2/backtest/engine.py
  - EventDrivenEngine.run() currently returns aggregated result
  - Need to also return the daily return series per strategy (not just combined)
  - Add: return_series field to SimulationResult

backend/app/studio_v2/router.py
  - Import PortfolioEngine
  - Store self.portfolio_engine = PortfolioEngine() in __init__
  - Add to routes dict:
    "/api/v2/backtest/portfolio-run": (self.run_portfolio_backtest, "POST")
    "/api/v2/backtest/portfolio-result/{run_id}": (self.get_portfolio_result, "GET")
  - Add 2 handler methods
```

### Integration Pattern

Direct handlers — portfolio backtest has orchestration logic distinct from single-strategy backtest.

### API Routes

```
POST /api/v2/backtest/portfolio-run
  Body: {
    "composition_id": "comp_123",
    "config": {
      "date_range": { "start": "2020-01-01", "end": "2025-12-31" },
      "benchmark": "SPY",
      "cost_model": "almgren_chriss"
    }
  }
  Response: {
    "run_id": "run_789",
    "combined": {
      "equity_curve": [{ "date": "2020-01-01", "value": 1.0 }, ...],
      "sharpe": 1.42,
      "sortino": 1.88,
      "max_drawdown_pct": -12.3,
      "calmar": 0.85
    },
    "per_strategy": [
      { "strategy_id": "strat_0", "name": "Momentum", "sharpe": 1.1, "equity_curve": [...] },
      { "strategy_id": "strat_1", "name": "MeanRev", "sharpe": 0.9, "equity_curve": [...] },
      { "strategy_id": "strat_2", "name": "VolCarry", "sharpe": 1.3, "equity_curve": [...] }
    ],
    "correlation_matrix": [
      { "strategy_a": "strat_0", "strategy_b": "strat_1", "rho": 0.15 },
      { "strategy_a": "strat_0", "strategy_b": "strat_2", "rho": 0.72 },
      { "strategy_a": "strat_1", "strategy_b": "strat_2", "rho": -0.08 }
    ],
    "redundancy_flags": [
      { "pair": ["strat_0", "strat_2"], "rho": 0.72, "threshold": 0.7, "redundant": true }
    ]
  }

GET /api/v2/backtest/portfolio-result/{run_id}
  Response: full PortfolioResult
```

---

## F2.10 — Sector/Factor Attribution Breakdown (Brinson-style)

### What It Is

Decomposes total portfolio return into two components: allocation effect (how much return comes from over/underweighting sectors or factors relative to the benchmark) and selection effect (how much return comes from picking better stocks within each sector/factor bucket). Computed using the Brinson-Hood-Beebower methodology, the standard approach used by institutional performance attribution systems (Bloomberg PORT, FactSet, Axioma). Results are returned per GICS sector and per FF5 factor (market, size, value, profitability, investment).

### Why It Exists

A Sharpe of 1.5 tells you a strategy is profitable but not why. Sector/factor attribution tells the researcher whether the return comes from smart sector allocation (e.g., overweighing tech in 2023) or genuine stock selection skill within sectors. This is the single most common question allocators ask: "Did this manager outperform because they were right about sectors, or because they picked good stocks?" Bloomberg PORT charges $6,000/seat/year for exactly this analysis.

### What It Does

1. Accepts a backtest run ID
2. Loads the portfolio's daily holdings and returns
3. For each GICS sector: computes the portfolio's weight vs benchmark weight (allocation effect) and the portfolio's sector return vs benchmark sector return (selection effect)
4. Same computation for FF5 factor tilts
5. Returns per-sector and per-factor breakdowns

### New Files to Create

```
backend/app/studio_v2/backtest/attribution.py
  - AttributionResult schema: sector[], factor[], benchmark_name
  - BrinsonAttribution class:
    - compute(run_id, benchmark_id) → AttributionResult
    - _sector_allocation_effect(portfolio_weights, bench_weights, sector_returns, bench_sector_returns)
    - _sector_selection_effect(portfolio_weights, sector_returns, bench_sector_returns)
    - _factor_allocation_effect(portfolio_factor_loadings, bench_factor_loadings, factor_returns)
    - _factor_selection_effect(portfolio_factor_loadings, factor_returns, bench_factor_returns)
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import BrinsonAttribution
  - Store self.attribution = BrinsonAttribution() in __init__
  - Add to routes dict:
    "/api/v2/backtest/attribution/{run_id}": (self.get_attribution, "GET")
  - Add 1 handler method
```

### Integration Pattern

Direct handler.

### API Routes

```
GET /api/v2/backtest/attribution/{run_id}
  Query: benchmark_id?
  Response: {
    "sector": [
      { "sector_name": "Technology", "allocation_effect_pct": 1.2, "selection_effect_pct": 0.8, "total_effect_pct": 2.0, "portfolio_weight_pct": 0.25, "benchmark_weight_pct": 0.20 },
      { "sector_name": "Healthcare", "allocation_effect_pct": -0.3, "selection_effect_pct": 0.5, "total_effect_pct": 0.2, ... },
      ...
    ],
    "factor": [
      { "factor_name": "Market Beta", "allocation_effect_pct": 1.5, "selection_effect_pct": 0.1, "total_effect_pct": 1.6 },
      { "factor_name": "Size (SMB)", "allocation_effect_pct": -0.2, "selection_effect_pct": 0.3, "total_effect_pct": 0.1 },
      ...
    ],
    "benchmark_name": "SPY",
    "total_allocation_effect": 0.9,
    "total_selection_effect": 1.1,
    "total_excess_return": 2.0
  }
```

---

## F2.11 — Slippage/Execution Quality Post-Mortem

### What It Is

Compares the backtest's modeled fill prices (from the Almgren-Chriss cost model) against a "realistic broker" reference fill estimate computed using actual historical bid-ask spread data and volume-weighted average prices for the same trades. Outputs a per-trade slippage delta table showing, for every trade in the backtest, what the model thought it would pay vs. what a realistic broker fill would have cost. The aggregate summary tells the researcher whether their strategy's modeled costs were meaningfully optimistic — a critical honesty check that most backtests never get.

### Why It Exists

The #1 reason strategies fail in live trading is that backtest cost models are too optimistic. The Almgren-Chriss model is the industry standard, but it requires calibrated parameters (lambda, spread) that most researchers guess. This feature replaces the guess with an empirical check: for each historical trade in the backtest, what was the actual quoted spread at that moment? If the model assumed 2 bps of slippage but the actual spread was 8 bps, that trade's profitability is misstated.

### What It Does

1. Loads the trade log from a backtest run
2. For each trade, looks up the historical bid-ask spread and VWAP for that ticker on that date
3. Computes a "realistic fill" = VWAP + (sign * half_spread * 0.5) — conservative assumption that fills occur in the middle 50% of the spread
4. Computes slippage delta = modeled_fill - realistic_fill (as basis points)
5. Aggregates across all trades: average slippage, total modeled cost, total realistic cost
6. Flags the strategy if modeled costs < 70% of realistic costs

### New Files to Create

```
backend/app/studio_v2/backtest/slippage_audit.py
  - TradeSlippage schema: trade_id, ticker, date, direction, size, modeled_fill, realistic_fill, slippage_bps
  - AggregateSlippage schema: total_trades, avg_slippage_bps, total_modeled_cost_bps, total_realistic_cost_bps, optimistic_bias_bps, verdict
  - SlippageAuditor class:
    - audit(run_id) → { per_trade: TradeSlippage[], aggregate: AggregateSlippage }
    - _estimate_realistic_fill(ticker, date, direction) → uses historical spread + VWAP
    - _verdict(bias_bps, total_realistic_cost) → "realistic" | "slightly_optimistic" | "overoptimistic"
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import SlippageAuditor
  - Store self.slippage_auditor = SlippageAuditor() in __init__
  - Add to routes dict:
    "/api/v2/backtest/slippage-audit/{run_id}": (self.get_slippage_audit, "GET")
  - Add 1 handler method
```

### Integration Pattern

Direct handler.

### API Routes

```
GET /api/v2/backtest/slippage-audit/{run_id}
  Response: {
    "per_trade": [
      { "trade_id": "T-001", "ticker": "AAPL", "date": "2023-06-15", "direction": 1, "size": 1000,
        "modeled_fill": 185.20, "realistic_fill": 185.35, "slippage_bps": 0.81 },
      ...
    ],
    "aggregate": {
      "total_trades": 245,
      "avg_slippage_bps": 1.2,
      "total_modeled_cost_bps": 185,
      "total_realistic_cost_bps": 294,
      "optimistic_bias_bps": 109,
      "verdict": "slightly_optimistic"
    }
  }
```

---

## F2.12 — Tax-Aware Backtesting Mode

### What It Is

An optional toggle that applies US-style tax treatment to the simulated trade log. It classifies each trade as short-term (held less than 1 year, taxed at ordinary income rates) or long-term (held 1+ years, taxed at lower capital gains rates), with both rates user-configurable. It also detects wash sales: under US tax rules, a loss on a security cannot be recognized if the same security is repurchased within 30 days before or after the sale. The disallowed loss is added to the cost basis of the replacement shares, effectively deferring the tax benefit. The output is a post-tax equity curve alongside the standard pre-tax curve, plus a wash-sale violation count and log.

### Why It Exists

Taxes are real and material. For a quantitatively managed portfolio, the difference between pre-tax and post-tax returns can be 1-3% annually depending on turnover rate, holding period mix, and tax rate. Most backtesting platforms ignore taxes entirely, meaning strategies with high turnover look more profitable than they actually are after tax. Institutional platforms like FactSet offer tax-aware performance reporting as a premium add-on. This feature makes it a toggle.

### What It Does

1. Accepts a tax configuration with short-term rate, long-term rate, and wash-sale detection flag
2. After the backtest simulation completes, processes the trade log through the tax engine
3. Classifies each trade as ST or LT based on holding period in calendar days
4. Applies wash-sale detection: for each loss sale, checks if the same ticker was repurchased within ±30 calendar days
5. Computes post-tax P&L for each trade
6. Builds a post-tax equity curve from the post-tax trade P&Ls
7. Returns both pre-tax and post-tax curves, wash-sale violations, and a summary

### New Files to Create

```
backend/app/studio_v2/backtest/tax_engine.py
  - TaxConfig schema: st_rate, lt_rate, wash_sale_detection
  - WashSale schema: trade_id, ticker, sale_date, repurchase_date, loss_disallowed
  - TaxReport schema: pre_tax_metrics, post_tax_metrics, wash_sales[], summary
  - TaxEngine class:
    - apply_tax(trade_log, config) → post_tax_equity_curve
    - _classify_st_lt(entry_date, exit_date) → "ST" | "LT"
    - _detect_wash_sales(trade_log) → WashSale[]
    - _compute_summary(pre_tax, post_tax, wash_sales)
```

### Files to Modify

```
backend/app/studio_v2/backtest/engine.py
  - Extend SimulationConfig to accept optional tax_config field
  - After the main simulation loop, if tax_config is set:
    - Pass the trade log through TaxEngine.apply_tax()
    - Add post_tax_equity_curve to SimulationResult

backend/app/studio_v2/router.py
  - The existing POST /api/v2/backtest/run route already accepts SimulationConfig
  - Just need to ensure tax_config fields are accepted by the existing route
  - Add to routes dict:
    "/api/v2/backtest/tax-report/{run_id}": (self.get_tax_report, "GET")
  - Add 1 handler method to query stored tax data from the run
```

### Integration Pattern

Tax integration happens inside the existing `POST /api/v2/backtest/run` route by extending `SimulationConfig`. The additional GET route is a separate handler.

### API Routes

```
POST /api/v2/backtest/run
  Extended body now accepts (tax_config is optional):
  {
    "strategy_source": "strategies/momentum.py",
    ... existing fields ...,
    "tax_config": {
      "st_rate": 0.35,
      "lt_rate": 0.20,
      "wash_sale_detection": true
    }
  }
  Response augmented with:
  {
    ... existing response ...,
    "post_tax_equity_curve": [{"date": "2020-01-01", "value": 1.0}, ...],
    "wash_sale_count": 12
  }

GET /api/v2/backtest/tax-report/{run_id}
  Response: {
    "pre_tax": { "total_return_pct": 85.2, "sharpe": 1.42, "equity_curve": [...] },
    "post_tax": { "total_return_pct": 71.8, "sharpe": 1.18, "equity_curve": [...] },
    "wash_sales": [
      { "trade_id": "T-045", "ticker": "AAPL", "sale_date": "2023-06-15",
        "repurchase_date": "2023-07-05", "loss_disallowed": 1250.00 }
    ],
    "summary": {
      "st_gains": 45000,
      "lt_gains": 12000,
      "total_tax_paid": 18150,
      "effective_tax_rate": 0.28
    }
  }
```

---

## F2.13 — Scenario/Stress Replay

### What It Is

A library of one-click historical scenario windows — the 2008 Global Financial Crisis (Sep 2008 – Mar 2009), the March 2020 COVID crash, the 2022 rate-hike drawdown, the 2015 China devaluation, and the dot-com crash (2000–2002). Each scenario re-runs the exact strategy configuration but restricted to that specific historical window, regardless of the strategy's original backtest date range. The output is the scenario-specific equity curve, max drawdown, and recovery time. Multiple scenarios can be run in parallel and viewed as a small-multiples grid.

### Why It Exists

A strategy that works from 2010–2025 might fail catastrophically during the 2008 GFC or the 2020 COVID crash. Most researchers test over their full date range and never isolate specific crisis periods. This feature makes it trivial to answer "how does my strategy handle the worst moments in market history?" — the kind of question every allocator asks and every risk committee wants documented.

### What It Does

1. Lists available crisis scenario definitions with their date ranges
2. Runs a strategy against a selected scenario by restricting the engine's date range to the scenario's window
3. Returns scenario-specific equity curve, max drawdown, and recovery time
4. Multiple scenarios can be run and their results stored for grid comparison

### New Files to Create

```
backend/app/studio_v2/backtest/scenarios.py
  - Scenario schema: id, name, description, start_date, end_date, events[]
  - ScenarioReplay class:
    - list_scenarios() → Scenario[]
    - replay(strategy_id, scenario_id) → run engine with scenario date range
    - get_result(run_id) → scenario result
  - Built-in scenarios:
    - "gfc_2008": 2008-09-01 to 2009-03-31, ["Lehman bankruptcy", "TARP", "Market bottom"]
    - "covid_2020": 2020-02-15 to 2020-04-30, ["COVID declared pandemic", "Circuit breakers", "Fed emergency"]
    - "rate_hike_2022": 2022-01-01 to 2022-10-31, ["First rate hike", "Inflation peak", "USD strength"]
    - "china_deval_2015": 2015-08-01 to 2016-02-29, ["PBOC devaluation", "Commodity crash", "China growth scare"]
    - "dotcom_2000": 2000-03-01 to 2002-10-31, ["Nasdaq peak", "Enron collapse", "9/11", "Accounting scandals"]
```

### Files to Modify

```
backend/app/studio_v2/backtest/engine.py
  - SimulationConfig needs an optional date_range_override field
  - If set, ignore the default date range and use only this window
  - This is already partially supported — just formalize it

backend/app/studio_v2/router.py
  - Import ScenarioReplay
  - Store self.scenarios = ScenarioReplay() in __init__
  - Add to routes dict:
    "/api/v2/backtest/scenarios": (self.list_scenarios, "GET")
    "/api/v2/backtest/scenarios/{scenario_id}/replay/{strategy_id}": (self.replay_scenario, "POST")
    "/api/v2/backtest/scenarios/result/{run_id}": (self.get_scenario_result, "GET")
  - Add 3 handler methods
```

### Integration Pattern

Direct handlers.

### API Routes

```
GET /api/v2/backtest/scenarios
  Response: [
    { "id": "gfc_2008", "name": "2008 Global Financial Crisis",
      "description": "Lehman failure, TARP, market bottom at S&P 666",
      "start_date": "2008-09-01", "end_date": "2009-03-31",
      "events": ["Lehman bankruptcy (Sep 15)", "TARP signed (Oct 3)", "S&P bottom (Mar 9)"] },
    ...
  ]

POST /api/v2/backtest/scenarios/{scenario_id}/replay/{strategy_id}
  Response: {
    "run_id": "run_scenario_001",
    "scenario_id": "gfc_2008",
    "strategy_id": "strat_abc",
    "equity_curve": [{ "date": "2008-09-01", "value": 1.0 }, ...],
    "max_drawdown_pct": -35.2,
    "recovery_days": 180,
    "metrics": { "sharpe": -0.42, "sortino": -0.55, "calmar": -0.28 }
  }

GET /api/v2/backtest/scenarios/result/{run_id}
  Response: full scenario result data
```

---

## F2.14 — Strategy Comparison Mode

### What It Is

A side-by-side view of 2–5 selected strategies (or runs from Model Lineage) showing their metrics in parallel columns, a correlation matrix of their return series, and combined/overlaid equity curve charts. The researcher can sort the comparison by any metric.

### Why It Exists

Researchers regularly need to compare multiple candidate strategies or multiple iterations of the same strategy (before and after parameter changes). Without this feature, they manually flip between tabs or export to a spreadsheet.

### What It Does

1. Accepts a list of run IDs
2. Queries each run's metrics and daily equity curve from Model Lineage
3. Computes pairwise correlation of daily returns
4. Returns all data in a single response for the frontend to render

### New Files to Create

None — this is a thin orchestration layer over existing lineage queries.

### Files to Modify

```
backend/app/studio_v2/backtest/lineage.py
  - Add batch_get_metrics(run_ids: list) → { run_id: { sharpe, sortino, max_dd, ... } }
  - Add batch_get_equity_curves(run_ids: list) → { run_id: [{ date, value }] }

backend/app/studio_v2/router.py
  - Add to routes dict:
    "/api/v2/backtest/compare": (self.compare_strategies, "POST")
  - Add 1 handler method:
    - Call lineage.batch_get_metrics(run_ids)
    - Call lineage.batch_get_equity_curves(run_ids)
    - Compute correlation matrix from equity curve daily returns
```

### Integration Pattern

Direct handler.

### API Routes

```
POST /api/v2/backtest/compare
  Body: { "run_ids": ["run_001", "run_002", "run_003"] }
  Response: {
    "metrics": [
      { "run_id": "run_001", "sharpe": 1.42, "sortino": 1.88, "max_dd_pct": -12.3, "calmar": 0.85, "dsr": 0.72, "pbo": 0.08 },
      { "run_id": "run_002", "sharpe": 0.95, "sortino": 1.22, "max_dd_pct": -18.7, "calmar": 0.52, "dsr": 0.45, "pbo": 0.22 },
      { "run_id": "run_003", "sharpe": 1.12, "sortino": 1.45, "max_dd_pct": -15.1, "calmar": 0.68, "dsr": 0.58, "pbo": 0.15 }
    ],
    "correlation_matrix": [
      { "run_a": "run_001", "run_b": "run_002", "rho": 0.15 },
      { "run_a": "run_001", "run_b": "run_003", "rho": 0.72 },
      { "run_a": "run_002", "run_b": "run_003", "rho": -0.08 }
    ],
    "equity_curves": {
      "run_001": [{ "date": "2020-01-01", "value": 1.0 }, ...],
      ...
    }
  }
```

---

## F3.10 — Data-Source Robustness Test

### What It Is

Re-runs the full backtest using a perturbed version of the price data — small random adjustments within the known precision/adjustment-methodology tolerance of the data source — across 200–500 simulations. This simulates what would happen if the strategy were evaluated on data from a slightly different vendor (e.g., Yahoo Finance vs. CRSP vs. Bloomberg adjusted closes, all of which differ by a few basis points due to differing dividend adjustment methodologies). Reports a data-sensitivity score: how much Sharpe degrades under plausible data-source variation alone.

### Why It Exists

Different data vendors apply different adjustment methodologies for splits and dividends, producing adjusted prices that can differ by 1-5 bps per corporate action event. Over a multi-year backtest, these small differences compound. A strategy that is hyper-sensitive to these tiny price variations is not robust — it is exploiting data-source-specific artifacts rather than genuine market signals. No existing quant platform provides this test.

### What It Does

1. Accepts a strategy file and perturbation parameters
2. For each simulation: generates a perturbed price series by adding Gaussian noise (std=0.001, the approximate cross-vendor disagreement) to daily returns
3. Runs the full backtest on the perturbed series
4. Records the resulting Sharpe
5. After N simulations (default 500), computes: sensitivity score (1.0 = completely insensitive, 0.0 = destroyed), baseline Sharpe, and distribution percentiles

### New Files to Create

```
backend/app/studio_v2/robustness/data_source_test.py
  - DataSourceResult schema: sensitivity_score, baseline_sharpe, sharpe_distribution, degradation, verdict
  - DataSourceRobustnessTest class:
    - run(strategy_file, n_simulations=500, noise_std=0.001)
    - _perturb_prices(original_prices, noise_std) → perturbed DataFrame
    - _run_single_sim(strategy_file, perturbed_prices) → Sharpe
    - _compute_sensitivity(baseline_sharpe, sharpe_distribution) → score
```

### Files to Modify

```
backend/app/studio_v2/shared/data_loader.py
  - Add get_perturbed_prices(ticker, start, end, noise_std) → DataFrame
  - Applies Gaussian noise to daily returns (not raw prices) to preserve price levels

backend/app/studio_v2/router.py
  - Extend the existing lazy_robustness method:
    - Import DataSourceRobustnessTest
    - Add to the if/elif chain: elif "data_source" in test:
    - route: "data_source" → DataSourceRobustnessTest().run(strategy_file, ...)
```

### Integration Pattern

Extended lazy dispatch — this follows the same pattern as the existing `lazy_robustness` method. The existing route `POST /api/v2/robustness/run-core-tests` already dispatches by `test` field. We add `"data_source"` to the dispatch chain.

### API Routes

```
POST /api/v2/robustness/run-core-tests
  Extended body: {
    "test": "data_source",
    "strategy_file": "strategies/momentum.py",
    "n_simulations": 500,
    "noise_std": 0.001
  }
  Response: {
    "sensitivity_score": 0.87,
    "baseline_sharpe": 1.42,
    "sharpe_distribution": { "p5": 1.12, "p25": 1.28, "p50": 1.38, "p75": 1.48, "p95": 1.55 },
    "degradation_pct": { "at_p50": 2.8, "at_p95": 8.5 },
    "verdict": "robust"
  }
```

---

## F3.11 — Look-Ahead Audit Trail Export

### What It Is

A signed, timestamped PDF or JSON report documenting every check the platform ran to confirm no future information leaked into the strategy. It collects evidence from: (1) the lookahead-linter results from Algorithm Lab (every warning and its resolution), (2) the event-driven engine's fill-timing guarantee (confirming fills happen at next-bar prices, not same-bar), and (3) the Purged K-Fold embargo settings used in any factor evaluation session. The report is cryptographically signed with SHA-256 and timestamp, making it a due-diligence artifact a researcher can hand to an allocator, auditor, or journal reviewer to prove the strategy has not been overfitted through data leakage.

### Why It Exists

Institutional allocators increasingly require data-integrity documentation before committing capital. The question "how do I know you didn't look ahead?" is the first one every due-diligence questionnaire asks. This feature produces a machine-verifiable answer, signed and timestamped, that covers every potential leakage channel the platform monitors.

### What It Does

1. Collects all lint warnings from the strategy's session history (from linter.py)
2. Confirms the engine's fill-timing configuration (fills at next open)
3. Documents any Purged K-Fold embargo settings used during factor evaluation
4. Packages everything into a structured report
5. Signs with SHA-256 hash + UTC timestamp
6. Returns as PDF or JSON

### New Files to Create

```
backend/app/studio_v2/robustness/audit_trail.py
  - AuditReport schema: report_id, strategy_id, sections[], signature, timestamp
  - AuditTrail class:
    - generate(strategy_id, run_ids?) → AuditReport
    - _collect_lint_evidence(linter, strategy_id) → section
    - _collect_engine_evidence(engine, run_ids) → section
    - _collect_cv_evidence(kernel, strategy_id) → section
    - _sign(report) → SHA-256 + timestamp
```

### Files to Modify

```
backend/app/studio_v2/algorithm_lab/linter.py
  - Add: get_lint_session_history(strategy_id) → structured log of all lint sessions
  - Currently linting runs on keystrokes and returns UI warnings
  - Need a persistent log that can be queried retroactively

backend/app/studio_v2/router.py
  - Import AuditTrail
  - Store self.audit_trail = AuditTrail() in __init__
  - Add to routes dict:
    "/api/v2/robustness/audit-trail/{strategy_id}": (self.generate_audit_trail, "POST")
  - Add 1 handler method
```

### Integration Pattern

Direct handler — the report generation is specific orchestration.

### API Routes

```
POST /api/v2/robustness/audit-trail/{strategy_id}
  Body: { "run_ids": ["run_001", "run_002"], "format": "pdf" }
  Response: application/pdf or application/json containing:
    {
      "report_id": "audit_20260728_abc123",
      "strategy_id": "strat_abc",
      "generated_at": "2026-07-28T14:30:00Z",
      "sections": [
        {
          "title": "Lookahead Linter Results",
          "findings": [
            { "check": "future_data_usage", "status": "pass", "detail": "No shift(-1) patterns detected" },
            { "check": "hardcoded_dates", "status": "pass", "detail": "No inline date ranges found" }
          ]
        },
        {
          "title": "Engine Fill Timing Guarantee",
          "config": { "fill_at": "next_open", "partial_fill": true, "adv_threshold": 0.2 }
        },
        {
          "title": "Purged K-Fold Embargo",
          "fold_count": 8,
          "embargo_days": 10,
          "purge_overlap": true
        }
      ],
      "signature": {
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "timestamp": "2026-07-28T14:30:00Z"
      }
    }
```

---

## F3.12 — Combinatorial Parameter Interaction Test

### What It Is

Extends the Parameter Stability Surface (existing Feature 3.2) by testing whether one parameter's sensitivity changes depending on a second parameter's value. For example, a lookback window of 20 days might produce a Sharpe of 1.5 when the threshold is 0.02, but a Sharpe of 0.3 when the threshold is 0.05. This interaction effect is invisible when each parameter is tested independently. The output is a 3D sensitivity surface (or sliced 2D surfaces at fixed values of the second parameter) with an interaction-effect score.

### Why It Exists

The standard Parameter Stability Surface (Feature 3.2) tests each parameter independently. But parameter interactions are common: a momentum strategy's optimal lookback depends on the volatility threshold used for entry. Detecting these interactions is critical because a strategy that looks stable when parameters are tested independently might be fragile when the interaction is exposed.

### What It Does

1. Accepts a strategy file and two parameter names
2. Creates an 11×11 grid (121 combinations) across each parameter's range
3. Runs the full backtest at every grid point
4. Computes the 3D surface: param_a × param_b → Sharpe
5. Computes marginal stability for each parameter (averaged across the other parameter's range)
6. Computes interaction score: how much the effect of param_a on Sharpe depends on param_b's value
7. Returns verdict: independent / interaction detected / strong interaction

### New Files to Create

```
backend/app/studio_v2/robustness/parameter_interaction.py
  - ParameterInteraction schema: param_a, param_b, grid_size, surface[], interaction_score, verdict
  - ParameterInteractionTest class:
    - run(strategy_file, param_a, param_b, grid_size=11) → ParameterInteraction
    - _build_grid(strategy_file, param_a, param_b, grid_size) → [{ a_val, b_val, sharpe }]
    - _compute_marginal_stability(grid, param) → score per param
    - _compute_interaction_score(grid) → float
    - _verdict(interaction_score) → "independent" | "interaction" | "strong_interaction"
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Extend lazy_robustness dispatch:
    - Import ParameterInteractionTest
    - Add: elif "parameter_interaction" in test:
    - route: "parameter_interaction" → ParameterInteractionTest().run(...)
```

### Integration Pattern

Extended lazy dispatch — same pattern as the existing `lazy_robustness` method. Add to the if/elif chain.

### API Routes

```
POST /api/v2/robustness/run-core-tests
  Extended body: {
    "test": "parameter_interaction",
    "strategy_file": "strategies/momentum.py",
    "param_a": "lookback",
    "param_b": "threshold",
    "grid_size": 11
  }
  Response: {
    "param_a": { "name": "lookback", "stability_score": 0.78 },
    "param_b": { "name": "threshold", "stability_score": 0.65 },
    "surface": [
      { "lookback": 10, "threshold": 0.01, "sharpe": 1.22 },
      { "lookback": 10, "threshold": 0.02, "sharpe": 1.35 },
      ...
    ],
    "interaction_score": 0.35,
    "verdict": "interaction"
  }
```

---

## F3.13 — Adversarial Stress Test

### What It Is

Constructs the worst plausible sequence of returns and costs within realistic historical bounds and evaluates whether the strategy survives it. Unlike Monte Carlo simulation (which randomly resamples historical returns), this test deliberately searches for the most damaging combination of return draws, volatility spikes, correlation breakdowns, and cost surges that remain within the realm of historical plausibility. It uses a constrained optimization over the historical parameter space — systematically selecting the 95th percentile volatility, 90th percentile costs, and maximum observed cross-asset correlation breakdown — to find the near-worst-case scenario.

### Why It Exists

Monte Carlo simulation answers "what's the typical range of outcomes?" but not "what's the worst case that is still historically plausible?" A strategy that passes 10,000 Monte Carlo paths might still fail catastrophically under a specific sequence that the random sampling was unlikely to draw. The adversarial test deliberately constructs that sequence.

### What It Does

1. Accepts a strategy file and constraint thresholds
2. Analyzes the historical returns, vol, and cost environment to identify percentile extremes
3. Searches over the historical parameter space to construct the worst-case sequence within constraints
4. Runs the strategy against the adversarial sequence
5. Returns survival verdict (did the strategy go bankrupt?), max drawdown, and comparison to baseline

### New Files to Create

```
backend/app/studio_v2/robustness/adversarial.py
  - AdversarialResult schema: survival, max_drawdown, recovery_possible, baseline, adversarial, degradation
  - AdversarialTest class:
    - run(strategy_file, constraints) → AdversarialResult
    - _build_worst_sequence(historical_data, constraints) → worst-case return + cost series
    - _run_strategy(strategy_file, sequence) → { sharpe, max_dd, terminal_value }
    - _compute_degradation(baseline, adversarial)
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import AdversarialTest
  - Add to routes dict:
    "/api/v2/robustness/adversarial": (self.run_adversarial, "POST")
    "/api/v2/robustness/adversarial/result/{run_id}": (self.get_adversarial_result, "GET")
  - Add 2 handler methods
```

### Integration Pattern

Direct handlers — this test is architecturally different from the parameter/timing perturbation tests (it uses optimization, not random sampling), so it gets its own routes rather than extending the lazy dispatch.

### API Routes

```
POST /api/v2/robustness/adversarial
  Body: {
    "strategy_file": "strategies/momentum.py",
    "constraints": {
      "max_vol_pctile": 95,
      "max_cost_pctile": 90,
      "max_corr_breakdown": 0.8
    }
  }
  Response: {
    "run_id": "adv_001",
    "survival": true,
    "max_drawdown_pct": -42.3,
    "recovery_possible": true,
    "estimated_recovery_days": 180,
    "baseline": { "sharpe": 1.42, "max_dd_pct": -12.3 },
    "adversarial": { "sharpe": -0.85, "max_dd_pct": -42.3 },
    "degradation_pct": 159.8,
    "verdict": "survives_adversarial"
  }

GET /api/v2/robustness/adversarial/result/{run_id}
  Response: full adversarial result data
```

---

## F4.12 — Factor Combination / Composite Score Builder

### What It Is

A panel where a researcher selects 2–10 factors (from the Sandbox session or the internal 40-factor baseline library) and combines them into a single composite score using a configurable weighting scheme: equal-weight (all factors contribute equally), IC-weighted (factors with higher historical IC get more weight), IC-IR-weighted (factors with higher risk-adjusted IC get more weight), or a custom Python combiner function written by the researcher. The composite score is then run through the exact same Instant IC Diagnostics (F4.2) and IC Decay Curve (F4.3) pipeline that any individual factor goes through, so a multi-factor composite gets identical statistical rigor as a single expression.

### Why It Exists

Real-world factors are almost never used in isolation. Funds run composite scores combining multiple signals. WorldQuant's WebSim allows combining factors but uses a proprietary black-box weighting. This feature makes the combination explicit, configurable, and testable with the same diagnostics that apply to individual factors.

### What It Does

1. Accepts a list of factor IDs (from Sandbox session or library)
2. Combines their factor scores using the chosen weight scheme
3. Runs the composite through the full IC/decay pipeline
4. Returns composite IC, IC-IR, decay curve, half-life, and optimal rebalance frequency

### New Files to Create

```
backend/app/studio_v2/factors/composite_combiner.py
  - CompositeScore schema: factor_ids, weights, composite_ic, composite_decay
  - CompositeCombiner class:
    - combine(factor_ids, weight_scheme) → composite daily series
    - _equal_weight(factor_scores) → daily averages
    - _ic_weighted(factor_scores, ics) → weighted by IC
    - _icir_weighted(factor_scores, icirs) → weighted by IC-IR
    - _custom_combiner(python_code, factor_scores) → weighted by user function
```

### Files to Modify

```
backend/app/studio_v2/factors/evaluator.py
  - Add evaluate_composite(composite_series) → { ic, icir, decay_curve, half_life }
  - Reuses existing compute_ic(), compute_decay_curve() methods

backend/app/studio_v2/router.py
  - Import CompositeCombiner
  - Add to the existing lazy_info dispatch table:
    - Add "composite" operation to the dispatch dict
    - Maps to: CompositeCombiner().combine() + evaluator.evaluate_composite()
```

### Integration Pattern

Extended lazy dispatch — add `"composite"` to the `lazy_info` dispatch table, following the same pattern as `"ic"`, `"decay"`, etc.

### API Routes

```
POST /api/v2/factors/evaluate
  Extended body: {
    "operation": "composite",
    "factor_ids": ["factor_001", "factor_002", "factor_003"],
    "weights": "ic_weighted"
  }
  Response: {
    "composite_id": "comp_factor_001",
    "component_weights": { "factor_001": 0.45, "factor_002": 0.35, "factor_003": 0.20 },
    "ic": { "naive": 0.052, "purged": 0.041, "icir": 0.38, "t_stat": 3.2, "p_value": 0.001 },
    "decay": { "half_life_days": 42, "best_model": "exponential", "optimal_rebalance_days": 21 }
  }
```

---

## F4.13 — Turnover-vs-Decay Tradeoff View

### What It Is

A chart plotting each factor's IC half-life against its position turnover rate. The turnover rate measures how much the factor's cross-sectional ranking changes from period to period — high turnover means the factor requires frequent rebalancing, which incurs transaction costs. The chart includes a shaded "uninvestable after costs" region computed using the platform's cost-break-even logic (Feature 3.6). A factor that plots in this region has a half-life so short and turnover so high that its gross IC is consumed by realistic transaction costs, making it undeployable regardless of gross IC.

### Why It Exists

A factor with IC 0.08 and half-life of 5 days looks good on paper, but if it requires daily rebalancing across 500 stocks, transaction costs will destroy the net return. This chart connects the Factor Sandbox's IC analysis to the Backtest Studio's cost model without requiring the researcher to run a full backtest.

### What It Does

1. Accepts a factor ID
2. Computes the factor's IC half-life (from F4.3)
3. Computes the factor's rank turnover rate (period-to-period rank correlation)
4. Estimates the break-even cost level using the platform cost model
5. Returns whether the factor is implementable net of realistic costs

### New Files to Create

```
backend/app/studio_v2/factors/turnover_estimator.py
  - TurnoverDecayResult schema: half_life, turnover_rate, break_even_cost, realistic_cost, implementable
  - TurnoverEstimator class:
    - compute_tradeoff(factor_id) → TurnoverDecayResult
    - _compute_turnover(factor_series) → rank autocorrelation → annualized turnover
    - _estimate_break_even(half_life, turnover) → cost bps
    - _check_implementable(break_even, realistic_cost_band) → bool
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import TurnoverEstimator
  - Add to the existing lazy_info dispatch table:
    - Add "turnover_decay" operation
```

### Integration Pattern

Extended lazy dispatch — add `"turnover_decay"` to `lazy_info`'s dispatch dict.

### API Routes

```
GET /api/v2/factors/ic-diagnostics
  Extended query: { "operation": "turnover_decay", "factor_id": "factor_001" }
  Response: {
    "factor_id": "factor_001",
    "half_life_days": 42,
    "turnover_rate_pct": 0.35,
    "break_even_cost_bps": 8.5,
    "realistic_cost_bps": 5.2,
    "implementable": true,
    "chart_region": [
      { "turnover": 0.1, "cost_bps": 3.0, "shaded": false },
      { "turnover": 0.3, "cost_bps": 6.0, "shaded": false },
      { "turnover": 0.5, "cost_bps": 12.0, "shaded": true }
    ]
  }
```

---

## F4.14 — Factor Library Governance Panel

### What It Is

A version history view for every factor in the internal 40-factor baseline library. Each factor's record shows: who modified it, when, what changed (full changelog of formula edits), and its current approval status (proposed/approved/deprecated). Deprecating a factor removes it from future orthogonalization baselines (so it no longer contributes to the Gram-Schmidt basis) while preserving all historical runs that referenced it — past results remain reproducible even after the factor is removed from active use.

### Why It Exists

Over time, some factors become obsolete (e.g., a momentum factor computed differently becomes the new standard) or are discovered to contain errors. Removing them from the library without governance breaks historical reproducibility. This panel solves both problems: factors have an audit trail, and deprecation preserves the past while cleaning the present.

### What It Does

1. Lists version history for a factor (every edit tracked)
2. Approves a factor (sets status to "approved" with reviewer name)
3. Deprecates a factor (sets status to "deprecated," removes from orthogonalization baseline, preserves historical runs)
4. Returns full changelog

### New Files to Create

```
backend/app/studio_v2/factors/governance.py
  - FactorVersion schema: version_number, expression, metrics_snapshot, modified_by, modified_at, changelog
  - FactorGovernance class:
    - get_versions(factor_id) → FactorVersion[]
    - approve(factor_id, reviewer) → update status
    - deprecate(factor_id, reason) → update status, remove from baseline
    - get_changelog(factor_id) → detailed edit history
```

### Files to Modify

```
backend/app/studio_v2/factors/library.py
  - Every time a factor is created or edited, the library should call governance to record a version
  - When computing orthogonalization basis, filter out deprecated factors

backend/app/studio_v2/router.py
  - Import FactorGovernance
  - Add to the existing routes dict (not lazy — these are specific CRUD operations):
    "/api/v2/factors/library/{id}/versions": (self.get_factor_versions, "GET")
    "/api/v2/factors/library/{id}/approve": (self.approve_factor, "POST")
    "/api/v2/factors/library/{id}/deprecate": (self.deprecate_factor, "POST")
    "/api/v2/factors/library/{id}/changelog": (self.get_factor_changelog, "GET")
  - Add 4 handler methods
```

### Integration Pattern

Direct handlers — these are specific CRUD/governance operations that deserve their own endpoints, not lazy dispatch.

### API Routes

```
GET /api/v2/factors/library/{id}/versions
  Response: [
    { "version": 1, "expression": "ts_mean(returns, 20)", "ic": 0.045, "modified_by": "alice", "modified_at": "2025-06-01T10:00:00Z", "changelog": "Initial version" },
    { "version": 2, "expression": "ts_mean(returns, 21)", "ic": 0.047, "modified_by": "bob", "modified_at": "2025-07-15T14:30:00Z", "changelog": "Changed lookback from 20 to 21" }
  ]

POST /api/v2/factors/library/{id}/approve
  Body: { "reviewer": "alice" }
  Response: { "status": "approved", "approved_by": "alice", "approved_at": "2026-07-28T12:00:00Z" }

POST /api/v2/factors/library/{id}/deprecate
  Body: { "reason": "Superseded by improved momentum calculation in v3" }
  Response: { "status": "deprecated", "deprecated_at": "2026-07-28T12:00:00Z", "replaces_in_baseline": false, "historical_runs_preserved": true }

GET /api/v2/factors/library/{id}/changelog
  Response: [
    { "version": 1, "field": "expression", "old_value": null, "new_value": "ts_mean(returns, 20)", "changed_by": "alice", "changed_at": "..." },
    { "version": 2, "field": "expression", "old_value": "ts_mean(returns, 20)", "new_value": "ts_mean(returns, 21)", "changed_by": "bob", "changed_at": "..." }
  ]
```

---

## F5.7 — Multi-Objective Pareto Frontier View

### What It Is

Instead of optimizing a single blended scalar objective, this mode runs the Bayesian search tracking multiple objectives simultaneously — for example, Sharpe ratio, capacity ceiling (how much AUM the strategy can hold before costs destroy returns), and max drawdown. The output is the Pareto-efficient frontier: every parameter configuration for which no other configuration is strictly better on all objectives at once. The researcher can then pick a point on the frontier that matches their actual risk/capacity preference, rather than accepting whatever a single weighted objective happened to produce.

### Why It Exists

Single-objective optimization (e.g., "maximize Sharpe") can produce extreme parameter sets that maximize Sharpe but have tiny capacity or massive drawdowns. A Sharpe of 2.0 is worthless if the strategy can only hold $5M before costs destroy returns. Multi-objective optimization exposes this tradeoff directly.

### What It Does

1. Accepts parameter ranges and a list of objective names
2. Runs Bayesian search tracking all objectives simultaneously
3. Identifies the Pareto frontier (non-dominated points)
4. Returns frontier points + dominated points for comparison

### New Files to Create

```
backend/app/studio_v2/optimizer/multi_objective.py
  - ParetoResult schema: frontier[], dominated[], convergence
  - MultiObjectiveOptimizer class:
    - run(param_ranges, objectives, trial_budget) → ParetoResult
    - _pareto_dominance(point_a, point_b) → dominates | dominated | incomparable
    - _compute_frontier(all_points) → frontier subset
```

### Files to Modify

```
backend/app/studio_v2/optimizer/search.py
  - Extend OptimizerConfig: add objectives field (list instead of single target)
  - The Bayesian optimizer needs to support multiple tracking metrics

backend/app/studio_v2/router.py
  - Extend lazy_optimizer dispatch:
    - Add "pareto" mode to the if/elif chain
    - Import MultiObjectiveOptimizer
```

### Integration Pattern

Extended lazy dispatch — add `"pareto"` mode to the existing `lazy_optimizer` method, alongside `"bayesian"`, `"walk_forward"`, and `"cpcv"`.

### API Routes

```
POST /api/v2/optimizer/bayesian-search
  Extended body: {
    "mode": "pareto",
    "param_ranges": { "lookback": [10, 100], "threshold": [0.01, 0.05] },
    "objectives": ["sharpe", "capacity", "max_drawdown"],
    "trial_budget": 500
  }
  Response: {
    "pareto_frontier": [
      { "params": { "lookback": 42, "threshold": 0.02 }, "objectives": { "sharpe": 1.42, "capacity_m": 500, "max_dd_pct": -12.3 } },
      { "params": { "lookback": 63, "threshold": 0.03 }, "objectives": { "sharpe": 1.22, "capacity_m": 1200, "max_dd_pct": -8.5 } },
      ...
    ],
    "dominated": [...],
    "convergence": [{ "trial": 50, "hypervolume": 0.65 }, ...]
  }
```

---

## F5.8 — Ensemble/Parameter Averaging Mode

### What It Is

Instead of selecting a single "best" parameter set from a search (which is itself a form of overfitting to the search data), this mode takes the top N parameter configurations by objective score and offers two behaviors: (a) **ensemble mode** — runs all N configurations as an ensemble and averages their signal outputs at each rebalance date, or (b) **distribution mode** — reports the distribution of expected performance across the top N, producing an uncertainty band rather than a single point estimate.

### Why It Exists

Picking the single best trial from 500 trials is itself a meta-overfitting step: the best trial is likely lucky, not genuinely better. Ensembling across the top N is a well-known overfitting mitigation in machine learning, applied here to parameter selection.

### What It Does

1. Queries the trial registry for the session's completed trials
2. Sorts by objective score and takes the top N
3. In ensemble mode: runs each of the top N configs through the engine and averages signals
4. In distribution mode: computes performance metrics for each top-N config and returns the distribution

### New Files to Create

```
backend/app/studio_v2/optimizer/ensemble.py
  - EnsembleResult schema: mode, top_configs[], metrics | distribution
  - EnsembleOptimizer class:
    - build(session_id, top_n, mode) → EnsembleResult
    - _ensemble(top_configs) → combined signal
    - _distribution(top_configs) → metric distributions
```

### Files to Modify

```
backend/app/studio_v2/optimizer/verdict.py
  - TrialRegistry: add query_for_top_n(session_id, n, objective) → list of top trials

backend/app/studio_v2/router.py
  - Import EnsembleOptimizer
  - Add to routes dict:
    "/api/v2/optimizer/ensemble": (self.run_ensemble, "POST")
  - Add 1 handler method
```

### Integration Pattern

Direct handler.

### API Routes

```
POST /api/v2/optimizer/ensemble
  Body: { "session_id": "sess_abc", "top_n": 10, "mode": "distribution" }
  Response: {
    "mode": "distribution",
    "top_configs": [
      { "rank": 1, "params": { "lookback": 42, "threshold": 0.02 }, "sharpe": 1.42 },
      { "rank": 2, "params": { "lookback": 44, "threshold": 0.02 }, "sharpe": 1.38 },
      ...
    ],
    "distribution": {
      "sharpe": { "min": 1.12, "p25": 1.28, "p50": 1.35, "p75": 1.40, "max": 1.42, "std": 0.08 },
      "max_dd": { "min": -15.2, "p25": -13.8, "p50": -12.5, "p75": -11.2, "max": -10.1, "std": 1.5 }
    },
    "single_best_sharpe": 1.42,
    "ensemble_median_sharpe": 1.35,
    "overfitting_mitigation_note": "The range across top-10 configs (1.12-1.42) suggests moderate parameter sensitivity."
  }
```

---

## F5.9 — Optimizer Cross-Validation View

### What It Is

Compares the region of parameter space favored by Mode 1 (Bayesian search) against the region favored by Mode 2 (Walk-Forward validation) for the same strategy. The result is an overlay: Bayesian-preferred region in one color, Walk-Forward-preferred region in another, plotted on a parameter stability heatmap. When the two methods converge to the same region of parameter space, that is a strong robustness signal. When they diverge — Bayesian says "use lookback=42" but Walk-Forward says "use lookback=63" — that is surfaced as an explicit warning flag.

### Why It Exists

Bayesian search and Walk-Forward validation ask different questions and can produce different answers. Bayesian says "what parameters maximize in-sample performance?" Walk-Forward says "what parameters generalize best out-of-sample?" When they disagree, the researcher needs to know. This is currently an invisible failure mode — no platform exposes this comparison.

### What It Does

1. Runs Bayesian search on the strategy
2. Runs Walk-Forward optimization on the same strategy
3. Extracts the preferred parameter region from each method
4. Computes the overlap percentage
5. Returns overlay data for frontend rendering

### New Files to Create

```
backend/app/studio_v2/optimizer/cross_validation.py
  - CrossValidationResult schema: bayesian_region, walkforward_region, overlap_pct, verdict
  - CrossValidation class:
    - run(strategy_file, is_window, oos_window, bayesian_trials) → CrossValidationResult
    - _extract_region(trials, method) → { param: { mean, std, importance } }
    - _compute_overlap(region_a, region_b) → percentage
    - _verdict(overlap_pct) → "high_overlap" | "partial_overlap" | "divergent"
```

### Files to Modify

```
backend/app/studio_v2/optimizer/search.py
  - Add extract_preferred_region(session_id) → { param: { mean, std, importance } }
  - This summarizes where the Bayesian search concentrated its trials

backend/app/studio_v2/router.py
  - Import CrossValidation
  - Add to routes dict:
    "/api/v2/optimizer/cross-validate": (self.cross_validate_optimizer, "POST")
  - Add 1 handler method
```

### Integration Pattern

Direct handler — this is an orchestration endpoint that coordinates both search modes.

### API Routes

```
POST /api/v2/optimizer/cross-validate
  Body: {
    "strategy_file": "strategies/momentum.py",
    "is_window_months": 24,
    "oos_window_months": 6,
    "bayesian_trials": 200
  }
  Response: {
    "bayesian": {
      "preferred_region": { "lookback": { "mean": 42, "std": 5, "importance": 0.8 }, "threshold": { "mean": 0.02, "std": 0.005, "importance": 0.6 } }
    },
    "walkforward": {
      "preferred_region": { "lookback": { "mean": 45, "std": 8, "importance": 0.7 }, "threshold": { "mean": 0.025, "std": 0.008, "importance": 0.5 } }
    },
    "overlap_pct": 78.5,
    "verdict": "high_overlap",
    "warning": null
  }
```

---

## F6.11 — Multi-Asset-Class Universe Support

### What It Is

Extends the Filter Stack Interface (Feature 6.1) to support futures, crypto, and FX alongside the existing equity universe builder. Each asset class gets its own filter primitives appropriate to that class: futures have contract expiry month and roll methodology selection (front-month, volume-weighted, or fixed-day roll), crypto pairs have exchange and quote currency filters, FX pairs have settlement type (spot/forward/NDF). Futures also require continuous contract construction — stitching individual contracts together into a continuous price series by switching from expiring to next contract on the roll date.

### Why It Exists

Many strategies operate across asset classes — a global macro strategy might trade equity index futures, FX forwards, and commodity futures simultaneously. Without multi-asset support, the platform is equities-only, which cuts off a massive portion of systematic trading strategies.

### New Files to Create

```
backend/app/studio_v2/data_studio/multi_asset.py
  - AssetClass schema: id, name, filter_primitives[]
  - MultiAssetUniverse class:
    - get_asset_classes() → AssetClass[]
    - build_futures_universe(tickers, roll_method, start, end) → continuous prices
    - build_crypto_universe(pairs, exchange, start, end) → price series
    - build_fx_universe(pairs, settlement, start, end) → price series
    - _front_month_roll(contracts) → price series switching at expiry
    - _volume_weighted_roll(contracts) → blend contracts by volume
    - _fixed_day_roll(contracts, day) → switch on fixed day before expiry
```

### Files to Modify

```
backend/app/studio_v2/data_studio/universe.py
  - Extend UniverseBuilder to accept asset_class parameter
  - Dispatch to MultiAssetUniverse when asset_class != "equity"

backend/app/studio_v2/shared/data_loader.py
  - Add: get_futures_data(continuous_ticker, roll_method) → DataFrame
  - Add: get_crypto_data(pair, exchange) → DataFrame
  - Add: get_fx_data(pair, settlement) → DataFrame

backend/app/studio_v2/shared/liquidity.py
  - Extend ADV/vol computation to futures (use contract volume), crypto (use exchange volume), FX (use estimated turnover)

backend/app/studio_v2/router.py
  - Import MultiAssetUniverse
  - Add to routes dict:
    "/api/v2/data-studio/asset-classes": (self.get_asset_classes, "GET")
  - Add 1 handler method
```

### Integration Pattern

Direct handler for the asset-classes listing. The universe build already uses `lazy_info` dispatch with `"universe"` operation — extend that to accept `asset_class` in the request.

### API Routes

```
GET /api/v2/data-studio/asset-classes
  Response: [
    { "id": "equity", "name": "Equities", "filters": [{ "id": "market_cap", "name": "Market Cap", "type": "range" }, { "id": "sector", "name": "GICS Sector", "type": "multiselect" }, ...] },
    { "id": "futures", "name": "Futures", "filters": [{ "id": "contract_month", "name": "Contract Month", "type": "select" }, { "id": "roll_method", "name": "Roll Methodology", "type": "select", "options": ["front_month", "volume_weighted", "fixed_day"] }, ...] },
    { "id": "crypto", "name": "Crypto", "filters": [{ "id": "exchange", "name": "Exchange", "type": "select" }, ...] },
    { "id": "fx", "name": "FX", "filters": [{ "id": "settlement", "name": "Settlement", "type": "select", "options": ["spot", "forward", "ndf"] }, ...] }
  ]
```

---

## F6.12 — Corporate Event Calendar Overlay

### What It Is

An overlay toggle in Data Explorer and the Backtest tearsheet that marks earnings dates, index-rebalance dates, and dividend ex-dates directly on the price/equity-curve timeline as vertical markers. This lets a researcher visually check whether their signal's apparent edge clusters suspiciously around known calendar events — a common hidden confound where a strategy appears to generate alpha but is actually capturing earnings drift (profits from stocks moving on earnings announcements) or rebalance arbitrage (profits from index inclusion effects).

### Why It Exists

It is remarkably common for a "momentum" strategy to actually be an "earnings drift" strategy — most of its profits come from holding stocks through earnings announcements. Without overlaying earnings dates on the equity curve, this confound is invisible.

### What It Does

1. Accepts a ticker and date range
2. Returns all corporate events for that ticker within the date range
3. Events have types (earnings, dividend, index rebalance), descriptions, and importance levels
4. The frontend uses this data to render vertical markers on charts

### New Files to Create

```
backend/app/studio_v2/data_studio/event_calendar.py
  - Event schema: date, event_type, description, importance
  - EventCalendar class:
    - get_events(ticker, start_date, end_date) → Event[]
    - _get_earnings_dates(ticker) → from fundamentals data or known calendar
    - _get_dividend_dates(ticker) → from dividend history
    - _get_index_rebalance_dates() → known index rebalance schedule (e.g., 3rd Friday of month for S&P)
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import EventCalendar
  - Add to routes dict:
    "/api/v2/data-studio/events/{ticker}": (self.get_corporate_events, "GET")
  - Add 1 handler method
```

### Integration Pattern

Direct handler.

### API Routes

```
GET /api/v2/data-studio/events/{ticker}
  Query: start_date, end_date
  Response: [
    { "date": "2023-11-02", "event_type": "earnings", "description": "Q3 2023 Earnings", "importance": "high" },
    { "date": "2023-11-15", "event_type": "dividend", "description": "Ex-dividend $0.24", "importance": "medium" },
    { "date": "2023-12-15", "event_type": "index_rebalance", "description": "S&P 500 quarterly rebalance", "importance": "low" }
  ]
```

---

## F6.13 — Synthetic/Backfilled Data Flagging

### What It Is

Any date range where data was gap-filled, forward-filled, or otherwise synthetically constructed is visually distinguished in every chart that touches that data — a dashed line segment or a distinct marker color — rather than rendered identically to real observed data points. This applies in Data Explorer, factor IC charts, and backtest equity curves whenever the underlying data series contains synthetic ranges.

### Why It Exists

When a researcher uploads a CSV with missing dates and the platform forward-fills, those filled values are not real. If they are rendered identically to real data, the researcher may draw conclusions from patterns that are artifacts of the fill methodology. This is especially dangerous for IC calculations — forward-filled returns artificially reduce volatility and inflate IC.

### What It Does

1. A SyntheticDataTracker records every date range where data was synthetically constructed
2. The frontend queries this data and renders dashed markers on synthetic segments
3. Backtest and factor services use this data to flag runs that consumed synthetic data

### New Files to Create

```
backend/app/studio_v2/data_studio/synthetic_flagging.py
  - SyntheticRange schema: ticker, start_date, end_date, reason, method, filled_count
  - SyntheticDataTracker class:
    - record(ticker, start, end, reason, method, count)
    - get_ranges(ticker) → SyntheticRange[]
    - get_all_ranges() → { ticker: SyntheticRange[] }
```

### Files to Modify

```
backend/app/studio_v2/router.py
  - Import SyntheticDataTracker
  - Add to routes dict:
    "/api/v2/data-studio/synthetic-ranges/{ticker}": (self.get_synthetic_ranges, "GET")
  - Add 1 handler method
```

### Integration Pattern

Direct handler.

### API Routes

```
GET /api/v2/data-studio/synthetic-ranges/{ticker}
  Response: [
    { "start_date": "2023-06-10", "end_date": "2023-06-15", "reason": "forward_fill", "method": "ffill", "filled_days": 4 },
    { "start_date": "2024-01-01", "end_date": "2024-01-10", "reason": "gap_fill", "method": "linear_interpolation", "filled_days": 7 }
  ]
```

---

## NEW PAGE 7 — PORTFOLIO RISK MANAGEMENT

### What This Page Is

The missing aggregate layer. Every existing page treats one strategy (or one combined portfolio construct) in isolation. This page treats the researcher's entire live/candidate book as a single risk object. It aggregates all strategies tagged "Active" or "Deployed" (per Model Lineage tags) and computes portfolio-level risk metrics, correlation structure, exposure concentration, configurable limits with breach detection, and a unified alert feed.

---

### F7.1 — Aggregate VaR/CVaR Panel

#### What It Is

Computes portfolio-level Value at Risk and Conditional VaR (Expected Shortfall) across all currently "Active" or "Deployed" tagged strategies, using both a parametric (variance-covariance) method and a historical-simulation method side by side, at 95% and 99% confidence, over 1-day and 10-day horizons. The panel shows both methods because they answer different questions: parametric tells you what risk looks like under normal market conditions, historical simulation tells you what risk would have looked like under actual past market conditions.

#### New Files to Create

```
backend/app/studio_v2/portfolio_risk/__init__.py

backend/app/studio_v2/portfolio_risk/var_engine.py
  - VaRResult schema: parametric {}, historical {}, comparison
  - VaREngine class:
    - compute(confidence=95|99, horizon=1|10) → VaRResult
    - _parametric_var(returns_matrix, weights, confidence, horizon) → { var, cvar }
    - _historical_var(returns_matrix, weights, confidence, horizon) → { var, cvar }
```

#### Files to Modify

```
backend/app/studio_v2/backtest/lineage.py
  - Add get_active_strategies() → [{ run_id, name, tag, daily_returns, weights }]
  - Query lineage runs with tag "Active" or "Deployed"

backend/app/studio_v2/router.py
  - Import VaREngine, lineage
  - Add to routes dict:
    "/api/v2/portfolio-risk/active-strategies": (self.get_active_strategies, "GET")
    "/api/v2/portfolio-risk/var": (self.get_portfolio_var, "GET")
  - Add 2 handler methods
```

#### Integration Pattern

Direct handlers — these are Page 7 endpoints with no existing counterpart.

#### API Routes

```
GET /api/v2/portfolio-risk/active-strategies
  Response: {
    "strategies": [
      { "run_id": "run_001", "strategy_name": "Momentum v3", "tag": "Active",
        "daily_returns": [{ "date": "2025-01-01", "value": 0.001 }, ...],
        "current_weight": 0.4 },
      ...
    ]
  }

GET /api/v2/portfolio-risk/var
  Query: confidence=[95,99], horizon=[1,10]
  Response: {
    "parametric": { "confidence": 95, "horizon_days": 1, "var_pct": -1.82, "cvar_pct": -2.45 },
    "historical": { "confidence": 95, "horizon_days": 1, "var_pct": -2.15, "cvar_pct": -2.88 },
    "comparison": "historical_higher"
  }
```

---

### F7.2 — Cross-Strategy Correlation & Concentration Dashboard

#### What It Is

A live-updating correlation matrix across all active strategies' daily returns, plus a concentration panel showing exposure overlap — if three "different" strategies are all secretly long the same 20 large-cap tech names, this surfaces that overlap explicitly.

#### New Files to Create

```
backend/app/studio_v2/portfolio_risk/concentration.py
  - ConcentrationResult schema: correlation_matrix[], overlapping_positions[]
  - ConcentrationAnalyzer class:
    - correlation_matrix() → [[id_a, id_b, rho]]
    - overlapping_positions() → [{ ticker, weight, holders[] }]
```

#### Files to Modify

```
backend/app/studio_v2/robustness/tests.py
  - Export the concentration detection logic from UniversePerturbationTest
  - Make it available as a standalone utility for reuse here

backend/app/studio_v2/router.py
  - Import ConcentrationAnalyzer
  - Add to routes dict:
    "/api/v2/portfolio-risk/correlation": (self.get_cross_strategy_correlation, "GET")
    "/api/v2/portfolio-risk/concentration": (self.get_position_concentration, "GET")
  - Add 2 handler methods
```

#### API Routes

```
GET /api/v2/portfolio-risk/correlation
  Response: {
    "matrix": [
      { "strategy_a": "run_001", "strategy_b": "run_002", "rho": 0.35 },
      { "strategy_a": "run_001", "strategy_b": "run_003", "rho": 0.72 },
      ...
    ],
    "labels": [
      { "run_id": "run_001", "name": "Momentum v3" },
      ...
    ]
  }

GET /api/v2/portfolio-risk/concentration
  Response: {
    "overlapping": [
      { "ticker": "AAPL", "weight_in_portfolio_pct": 8.5,
        "holders": [
          { "strategy_id": "run_001", "weight_pct": 5.2, "name": "Momentum v3" },
          { "strategy_id": "run_002", "weight_pct": 3.3, "name": "MeanRev v2" }
        ]
      },
      ...
    ],
    "top_n": 20
  }
```

---

### F7.3 — Position & Exposure Limits Panel

#### What It Is

Configurable limits — max single-name weight, max sector weight, max gross/net leverage, max strategy-level VaR contribution — with real-time breach indicators. Any active strategy pushing the aggregate book over a limit is flagged with which limit and by how much.

#### New Files to Create

```
backend/app/studio_v2/portfolio_risk/limits.py
  - LimitConfig schema: max_single_name_pct, max_sector_pct, max_gross_leverage, max_net_leverage, max_strategy_var_pct
  - LimitBreach schema: limit_name, current_value, threshold, severity
  - ExposureLimits class:
    - get() → { limits, current_values, breaches }
    - update(new_limits) → save
    - check_breaches(active_strategies) → LimitBreach[]
    - _compute_current_values(active_strategies) → aggregate exposures
```

#### Files to Modify

```
backend/app/studio_v2/router.py
  - Import ExposureLimits
  - Add to routes dict:
    "/api/v2/portfolio-risk/limits": (self.get_limits, "GET")
    "/api/v2/portfolio-risk/limits": (self.update_limits, "PUT")
    "/api/v2/portfolio-risk/limits/breaches": (self.get_limit_breaches, "GET")
  - Add 3 handler methods
```

#### API Routes

```
GET /api/v2/portfolio-risk/limits
  Response: {
    "limits": { "max_single_name_pct": 5.0, "max_sector_pct": 25.0, "max_gross_leverage": 2.0, "max_net_leverage": 1.5, "max_strategy_var_pct": 40.0 },
    "current": { "max_single_name_pct": 4.2, "max_sector_pct": 28.0, "max_gross_leverage": 1.8, "max_net_leverage": 1.2, "max_strategy_var_pct": 35.0 },
    "breaches": [
      { "limit_name": "max_sector_pct", "current_value": 28.0, "threshold": 25.0, "severity": "WARN" }
    ]
  }

PUT /api/v2/portfolio-risk/limits
  Body: { "max_single_name_pct": 5.0, "max_sector_pct": 30.0 }
  Response: { "limits": { ...updated... } }

GET /api/v2/portfolio-risk/limits/breaches
  Response: { "breaches": [{ "limit_name": "max_sector_pct", "current_value": 28.0, "threshold": 25.0, "severity": "WARN", "breached_at": "...", "duration_seconds": 3600 }] }
```

---

### F7.4 — Real-Time Risk Alert Feed

#### What It Is

A running chronological log surfacing the moment any monitored condition crosses threshold — paper-trading divergence score, VaR breach, concentration limit breach, data freshness failure — all in one unified feed rather than scattered across separate pages.

#### New Files to Create

```
backend/app/studio_v2/portfolio_risk/alert_feed.py
  - Alert schema: id, type, severity, message, details, created_at, acknowledged
  - AlertFeed class:
    - get_alerts(since?, severity?, limit, offset) → paginated alerts
    - acknowledge(alert_id) → mark acknowledged
    - _ingest_from_var(vaREngine) → check VaR, create alerts
    - _ingest_from_limits(exposureLimits) → check breaches, create alerts
    - _ingest_from_reconciliation(divergence) → check paper trading divergence
    - _ingest_from_freshness(freshnessMonitor) → check data freshness
```

#### Files to Modify

```
backend/app/studio_v2/router.py
  - Import AlertFeed
  - Add to routes dict:
    "/api/v2/portfolio-risk/alerts": (self.get_risk_alerts, "GET")
    "/api/v2/portfolio-risk/alerts/{alert_id}/ack": (self.acknowledge_alert, "POST")
  - Add 2 handler methods
```

#### API Routes

```
GET /api/v2/portfolio-risk/alerts
  Query: since?, severity?, limit=50, offset=0
  Response: {
    "alerts": [
      { "id": "alert_001", "type": "limit_breach", "severity": "WARN",
        "message": "Sector limit breach: Technology at 28% (limit 25%)",
        "details": { "limit": "max_sector_pct", "current": 28.0, "threshold": 25.0 },
        "created_at": "2026-07-28T14:30:00Z", "acknowledged": false },
      ...
    ],
    "total": 12,
    "has_more": false
  }

POST /api/v2/portfolio-risk/alerts/{alert_id}/ack
  Response: { "acknowledged": true, "acknowledged_at": "2026-07-28T15:00:00Z" }
```

---

## CROSS-CUTTING

### F0.1 — Research Notebook / Journal Layer

#### What It Is

A persistent, freeform prose journal attached to the researcher's account (not to a single strategy file), where hypotheses, dead-end notes, and reasoning ("tried X because Y, abandoned because Z") can be written and optionally tagged to specific Model Lineage run IDs. Model Lineage currently records *what* was run and *when* — this records *why*, closing the single biggest gap between "a log of backtests" and "an actual research record" a fund would want for institutional memory and reproducibility of reasoning, not just of code.

#### New Files to Create

```
backend/app/studio_v2/services/journal_service.py
  - JournalEntry schema: id, title, body, tags, linked_run_ids, created_at, updated_at
  - JournalService class:
    - list(tag?, run_id?, date_from?, date_to?, limit, offset) → paginated entries
    - create(title, body, tags?, linked_run_ids?) → JournalEntry
    - update(id, title?, body?, tags?, linked_run_ids?) → JournalEntry
    - delete(id) → void
    - get_tags() → [{ tag, count, last_used }]
  - Backend storage: SQLite table
```

#### Files to Modify

```
backend/app/studio_v2/router.py
  - Import JournalService
  - Add to routes dict:
    "/api/v2/journal": (self.list_journal_entries, "GET")
    "/api/v2/journal": (self.create_journal_entry, "POST")
    "/api/v2/journal/{entry_id}": (self.update_journal_entry, "PUT")
    "/api/v2/journal/{entry_id}": (self.delete_journal_entry, "DELETE")
    "/api/v2/journal/tags": (self.get_journal_tags, "GET")
  - Add 5 handler methods
```

#### Integration Pattern

Direct handlers — standard CRUD.

#### API Routes

```
GET /api/v2/journal
  Query: tag?, run_id?, date_from?, date_to?, limit=50, offset=0
  Response: {
    "entries": [
      { "id": "entry_001", "title": "Why momentum lookback=42",
        "body_snippet": "Tested lookback values 10-100...",
        "tags": ["momentum", "parameter_selection"],
        "linked_run_ids": ["run_001", "run_002"],
        "created_at": "2026-07-28T10:00:00Z",
        "updated_at": "2026-07-28T11:30:00Z" },
      ...
    ],
    "total": 15,
    "has_more": false
  }

POST /api/v2/journal
  Body: { "title": "Why momentum lookback=42", "body": "Full reasoning...", "tags": ["momentum"], "linked_run_ids": ["run_001"] }
  Response: { "id": "entry_001", ...full entry... }

PUT /api/v2/journal/{entry_id}
  Body: { "body": "Updated reasoning..." }
  Response: { "id": "entry_001", ...updated... }

DELETE /api/v2/journal/{entry_id}
  Response: { "deleted": true, "id": "entry_001" }

GET /api/v2/journal/tags
  Response: [{ "tag": "momentum", "entry_count": 5, "last_used": "2026-07-28T11:30:00Z" }, ...]
```

---

## COMPLETE BACKEND BUILD SUMMARY

### New Service Files to Create (29)

| File | For Feature |
|------|-------------|
| `algorithm_lab/templates.py` | F1.10 |
| `algorithm_lab/portfolio_composer.py` | F1.11 |
| `algorithm_lab/collaboration.py` | F1.13 |
| `algorithm_lab/compute_budget.py` | F1.14 |
| `algorithm_lab/snippets.py` | F1.15 |
| `backtest/portfolio_engine.py` | F2.9 |
| `backtest/attribution.py` | F2.10 |
| `backtest/slippage_audit.py` | F2.11 |
| `backtest/tax_engine.py` | F2.12 |
| `backtest/scenarios.py` | F2.13 |
| `robustness/data_source_test.py` | F3.10 |
| `robustness/audit_trail.py` | F3.11 |
| `robustness/parameter_interaction.py` | F3.12 |
| `robustness/adversarial.py` | F3.13 |
| `factors/composite_combiner.py` | F4.12 |
| `factors/turnover_estimator.py` | F4.13 |
| `factors/governance.py` | F4.14 |
| `optimizer/multi_objective.py` | F5.7 |
| `optimizer/ensemble.py` | F5.8 |
| `optimizer/cross_validation.py` | F5.9 |
| `data_studio/multi_asset.py` | F6.11 |
| `data_studio/event_calendar.py` | F6.12 |
| `data_studio/synthetic_flagging.py` | F6.13 |
| `portfolio_risk/__init__.py` | P7 |
| `portfolio_risk/var_engine.py` | F7.1 |
| `portfolio_risk/concentration.py` | F7.2 |
| `portfolio_risk/limits.py` | F7.3 |
| `portfolio_risk/alert_feed.py` | F7.4 |
| `services/journal_service.py` | F0.1 |

### Existing Files to Modify (14)

| File | What Changes | For |
|------|-------------|-----|
| `router.py` | Add ~35 routes + imports + handler methods | All |
| `kernel.py` | Multi-strategy namespace isolation, compute budget integration | F1.11, F1.14 |
| `engine.py` | Per-strategy returns export, tax post-processing, date range override | F2.9, F2.12, F2.13 |
| `metrics.py` | Cross-strategy correlation method | F2.9 |
| `lineage.py` | Batch metrics query, batch equity curves, active strategy query | F2.14, F7.1 |
| `tests.py` (robustness) | Register data_source + parameter_interaction tests, export concentration utility | F3.10, F3.12, F7.2 |
| `linter.py` | Structured lint session history for audit | F3.11 |
| `evaluator.py` (factors) | Composite evaluation method | F4.12 |
| `library.py` | Governance integration hook on factor CRUD, deprecation filter in baseline | F4.14 |
| `search.py` | Multi-objective config support, preferred region extraction | F5.7, F5.9 |
| `data_loader.py` | Data perturbation utilities, futures/crypto/FX sources | F3.10, F6.11 |
| `liquidity.py` | Multi-asset ADV/vol calibration | F6.11 |
| `universe.py` | Asset class dispatch | F6.11 |

### Total New API Routes: 35

All specified above — each with full method, path, request body, and response shape.
