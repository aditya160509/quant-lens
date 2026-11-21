# Backend code standards and review method

**Scope:** `backend/main.py`, `backend/app/`, backend tests, and backend dependency, data, and deployment configuration. Use this guide when reviewing an individual file, implementing a backend backlog item, or preparing a backend release.

Apply this alongside [Studio Code Standards](CODE_STANDARDS.md), especially sections 2–8 for financial correctness and security and sections 11–15 for performance, tests and operations. Use the existing [project plan](../../plans/PLAN.md) and the [Dev Ideas backend backlog](../plan/DEV_IDEAS.md#backend-backlog-across-this-file) for implementation scope. A review finding documents work. It does not authorize unrelated edits, new dependencies, production configuration changes, or frontend changes.

## 1. Review a file

1. **Identify the contract.** Record the file, revision, responsibility, entry points and callers. Use the code graph first for discovery, then read the implementation, registration, tests and configuration. Follow one normal end-to-end path and one failure path. For a shared helper, check its different caller classes.
2. **Identify the risk.** Mark the applicable rows below. A file can have several roles. Record who controls its inputs, what it reads or writes, what can run concurrently, how work is bounded, and how it fails. Map numeric changes to their financial invariants.
3. **Gather the smallest sufficient evidence.** Use inspection for static properties, focused tests for executable contracts, and representative runtime measurements for resource claims. A workload-level benchmark can cover several files if it names the exercised path. Pure helpers generally need correctness tests and a complexity assessment.
4. **Record a verdict per applicable check.** Use **PASS** with evidence, **FAIL** with a finding, **N/A** with a reason, or **UNVERIFIED** with the missing evidence. Code reading can establish that a limit is configured. Exercise the limit to establish that it works. Record existing failures separately from regressions.
5. **Prioritize by consequence.** Use the Studio severity rules. P0 covers material financial misstatement, unauthorized access, isolation failure and silent corruption. P1 covers material correctness, reliability and performance failures. P2 covers lower-impact maintenance and efficiency. An applicable P0 or P1 without adequate evidence stays unresolved for the affected release.

| File or change | Minimum review evidence |
|---|---|
| Route, request model, middleware | Registered route and caller. Success, invalid input, relevant permission denial and response compatibility. Verify overload and cancellation boundaries for expensive work. |
| Engine, formula, indicator, ML or portfolio logic | Independent expected values, chronology and numerical edge cases. Check complexity at realistic dimensions and compare speed and peak memory for changed hot paths. |
| Store, migration, ingestion or cache | Keys, transaction and publication boundary, concurrent writer behavior where relevant, prior-format compatibility, recovery and stale-data behavior. |
| Worker, subprocess, queue or scheduler | State transitions, saturation, timeout and cancellation, retries, duplicate delivery, worker loss and resource cleanup. |
| Shared utility or serializer | Caller categories, boundary values, failure semantics, mutation behavior and complexity. |
| Test, fixture or configuration | Which contract it establishes, why expectations are independent, how failures surface, and whether defaults are safe in each supported environment. |

**Review record**

```text
File and revision:
Role, entry points and callers:
Inputs, side effects and resource bounds:
Check ID | PASS / FAIL / N/A / UNVERIFIED | Evidence or reason
Finding | P0 / P1 / P2 | file:line | impact | next action
Checks run and exit codes:
Shared benchmark or integration evidence:
Remaining release risks:
```

## 2. Code and runtime contracts

| ID | Check |
|---|---|
| BE-01 Design and compatibility | Keep HTTP validation, domain decisions, storage and execution responsibilities understandable. Reuse canonical financial logic. Trace public callers, persisted versions, request/response shapes and job states before changing them. Prefer explicit compatibility handling for older strategies and runs. |
| BE-02 Python semantics | Type boundary functions. Make units, mutability, shapes, nullability and ownership explicit. Use specific exceptions and preserve useful causes. Handle only failures the layer can interpret or recover from. Use context managers and deterministic cleanup. Review import-time I/O, initialization, hidden globals, and model or dataset duplication across workers. |
| BE-03 API limits and errors | Validate lengths, cardinality, ranges and cross-field constraints before allocating or scheduling work. Bound request bodies, batches, pagination, date ranges, symbols, result rows and response bytes where applicable. Keep stable error semantics. Separate validation, permission denial, conflict, timeout, saturation and internal failure. Check how streaming and polling clients behave when disconnected. Check per-principal quotas and process-wide limits independently. For a new error contract, evaluate RFC 9457 against existing clients and keep internal diagnostics out of response details. [OWASP resource consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) · [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) |
| BE-04 Identity and privacy | Enforce verified identity, object ownership and permissions at the server. Review HTTP, WebSocket, job, export and artifact access. Apply least privilege and isolate credentials from jobs. Prevent strategy source, tokens, customer data and protected hold-out results from leaking through errors, telemetry, caches or artifacts. Validate paths, archive limits, network destinations and query boundaries where applicable. Use versioned OWASP ASVS references for relevant controls. [OWASP ASVS](https://asvs.owasp.org/) |
| BE-05 Untrusted execution | Treat user strategies, cells and report scripts as untrusted. Require independently verified isolation before exposing them to untrusted users. Enforce bounds on CPU, memory, wall time, process count, output and allowed data. Verify cleanup of descendants and temporary files after cancellation, timeout and worker failure. Record the boundary actually deployed, including filesystem, network and secret access. Use approved defensive tests and controlled fixtures. [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) |
| BE-06 Async and concurrency | Trace each blocking operation in an async path. Keep blocking I/O and CPU-heavy numerical work off the API event loop. Set explicit ownership for tasks and bound queues, pools and outstanding I/O. Connect cancellation to the work owner. For shared state, use atomic operations or transactions and test concurrent access. Include native BLAS, OpenMP, Numba and model threads in the worker count. [FastAPI concurrency](https://fastapi.tiangolo.com/async/) · [FastAPI deployment](https://fastapi.tiangolo.com/deployment/concepts/) · [Numba threading](https://numba.readthedocs.io/en/stable/user/threading-layer.html) |
| BE-07 Deadlines, retries and jobs | Use a shared deadline across dependent calls, bounded timeouts and a documented retry owner. Retry eligible transient failures with backoff and jitter. Use stable idempotency keys and atomic deduplication for retried side effects, checking payload identity on key reuse. Define job states, terminal outcomes, lease or restart recovery and publication semantics. Treat queue time and execution time separately. [Amazon Builders’ Library on retries](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) · [Idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) |
| BE-08 Storage and migrations | Define keys, uniqueness, transactions and writer ownership. Keep transactions short and bound contention waits. Inspect representative query plans and confirm indexes against actual queries. For SQLite WAL stores, review checkpoint behavior, long-lived reads and backup consistency. Use approved expand/migrate/contract or another compatible migration path. Test upgrade from representative old data and exercise rollback or restore before a risky release. [SQLite WAL](https://sqlite.org/wal.html) · [Query plans](https://sqlite.org/eqp.html) · [Online Backup API](https://sqlite.org/backup.html) |
| BE-09 Data and cache lifecycle | Validate schema, identities, timestamps, units, duplicates and missingness at ingestion. Publish refreshes atomically and preserve the prior valid version on failure. Track coverage, freshness and provenance. Key caches on every material input, including caller scope where relevant, data version, algorithm and settings. Set size, lifetime and invalidation bounds. Check simultaneous misses and verify failed work does not publish partial results. |
| BE-10 Numerical and research integrity | Separate observation, availability, decision and execution times. Check warm-up, point-in-time joins, train/test and hold-out isolation, selection bias and trial accounting. Reconcile cash, equity, orders, positions and costs using independent fixtures. Define dtype, overflow, rounding, NaN and infinity behavior. Record seed, data identity, effective settings, engine version and justified tolerances. Use the canonical Studio definitions and fixtures. [Studio quant standards](CODE_STANDARDS.md#2-quantitative-research-integrity) · [Feast point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) |
| BE-11 Supply chain | Use the supported interpreter and lockfile. Review direct, transitive and native dependencies for provenance, license, advisories, wheel support and resource impact. Keep authorizations explicit for package additions and external services. Use the repository’s existing scanners and a clean environment for release evidence. [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final) |
| BE-12 Signals and recovery | Observe latency, traffic, errors and saturation. Distinguish route latency, queue wait, worker run time and end-to-end completion. Correlate requests and jobs with redacted logs and traces. Use route templates and bounded labels for metrics. Keep user IDs, run IDs and raw URLs out of metric labels. Define meaningful success indicators and error budgets with an owner. Verify alerts, readiness, graceful shutdown, backup restoration, and restart and rollback behavior for changed operational paths. [Google SRE monitoring](https://sre.google/sre-book/monitoring-distributed-systems/) · [Implementing SLOs](https://sre.google/workbook/implementing-slos/) · [OpenTelemetry HTTP metrics](https://opentelemetry.io/docs/specs/semconv/http/http-metrics/) |

## 3. Resource and performance review

| ID | Review question | Evidence |
|---|---|---|
| PERF-01 Complexity and CPU | How does work grow with bars, symbols, parameters, trials, features, jobs, or output rows? Are loops, joins, repeated compilation and serialization justified? Are threads oversubscribed? | State the dominant dimensions and expected complexity. Measure wall time and CPU seconds per completed workload, throughput per allocated core, and CPU throttling where deployed. Use `cProfile` or a suitable profiler on a separate diagnostic run. Check native hotspots separately if Python stacks cannot explain the cost. [Python profilers](https://docs.python.org/3.12/library/profile.html) · [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) |
| PERF-02 Memory and ownership | What is the largest live allocation? Which buffers coexist across conversion, worker transfer and response building? Which buffers, caches or results outlive the request? | Measure peak for the service and workers together and post-job memory after repeated runs. In Linux use scoped cgroup `memory.peak`, `memory.current` and `memory.events` when available. Attribute growth with `tracemalloc` snapshots, process RSS or PSS, and native allocation evidence as needed. RSS summed across processes can double-count shared pages. Python allocation traces cover only traced allocations. Estimate dense array memory as shape times dtype size, then confirm temporary copies and process replication empirically. [Python tracemalloc](https://docs.python.org/3.12/library/tracemalloc.html) · [NumPy copies and views](https://numpy.org/doc/stable/user/basics.copies.html) · [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) |
| PERF-03 I/O and storage | Does the path scan, fetch, copy or serialize more than it uses? Are disk growth, query contention and outbound concurrency bounded? | Record query count and timings, bytes read/written and returned, cache hit/miss behavior, and disk or network saturation when relevant. Compare representative query plans and cold vs warm runs. Exercise slow or unavailable dependencies. Test retention or pruning when persisted artifacts can grow. |
| PERF-04 Latency and capacity | What happens at steady use, burst load and sustained overload? Does expensive work impair unrelated interactive requests? | Report p50/p95/p99 only where samples support them, per-workload throughput, queue depth, error/timeout/rejection rates and recovery time. Measure enqueue-to-start, start-to-finish and client-observed completion. Run interactive traffic alongside jobs and separate offered load from achieved throughput. Verify queues and workers recover after saturation. |
| PERF-05 Guardrails and equivalence | Will input size, cancellation, failures or retries defeat resource limits? Does the optimization change the result? | Test limits at, below and above the boundary. Prove result equivalence with the same input and appropriate tolerances. Confirm cleanup on failure and timeout. Record trade-offs between latency, CPU, memory and I/O. |

### Repeatable benchmark procedure

1. **Choose workloads before measuring.** Use a small deterministic fixture for diagnosis, a representative workload for comparison and an upper supported workload for capacity. For Studio, separate compile/preview requests from backtests, sweeps, validation and sandboxed jobs when they use different resource paths. Include concurrent polling or interactive requests where relevant.
2. **Record the environment.** Capture revisions, Python/lockfile and native library versions, OS and CPU, available memory, cgroup limits, worker and thread counts, dataset identity and shape, random seed, cache state and benchmark command. Use equivalent baselines. Label laptop results as local. Validate deployment capacity on comparable infrastructure.
3. **Separate cold and steady-state paths.** Measure import/startup, first-job dataset load and JIT compilation separately from warmed requests. Run unprofiled timings for comparisons. Repeat under controlled conditions and report sample count, spread, errors and timeouts. Increase observations before interpreting a noisy p99.
4. **Measure the whole process group.** Use service-level memory and CPU during a mixed load test. For a leak, repeat the same jobs and inspect live allocations and post-quiescence memory. Allocator retention, caches, memory-mapped files and memory still held by workers can look similar at the RSS level.
5. **Exercise failure and recovery.** Use a controlled environment. Try worker loss, a slow dependency, cancellation during execution, failed storage writes and overload as applicable. Verify recovery, absence of duplicate results and return to a stable resource envelope.
6. **Assess against an agreed budget.** Record an absolute service or resource limit where one exists and allowable change from the measured baseline. If neither exists, record the baseline and leave budget compliance **UNVERIFIED**. Set budgets per workload and deployment. Avoid universal RAM, CPU or latency thresholds and noisy CI gates without a stable baseline.

| Workload and dataset | Limits and budget | Baseline | Candidate | Verdict |
|---|---|---|---|---|
| Name, input size, cache state, load and repetitions | SLO or limit, allowed regression and owner | Latency, CPU, peak memory, throughput, errors and relevant I/O | Same metrics, result-equivalence reference | PASS / FAIL / N/A / UNVERIFIED |

### Interpret the measurements

- **CPU utilization and work per job.** Use a monotonic elapsed clock such as `perf_counter_ns()` and report process CPU time separately. `process_time_ns()` covers the current process. For jobs running in child processes, measure the worker or use the Linux cgroup `cpu.stat` delta for the whole service. Divide CPU seconds by elapsed seconds to estimate average cores consumed and by completed jobs to estimate CPU cost per job. Report the scope, concurrency, timeouts and failures beside these ratios. On Linux, check resource pressure and throttling when latency rises. [Python clocks](https://docs.python.org/3.12/library/time.html) · [Linux pressure stall information](https://docs.kernel.org/accounting/psi.html)
- **Tail latency under overload.** Use controlled arrival-rate traffic when clients continue sending requests while the service slows. A fixed group of users waiting for each response models a different workflow and can understate the backlog under overload. Report dropped load-generator iterations and client-side timeouts. Use a sustained test that includes relevant cache, worker or checkpoint cycles when growth over time is a risk. [Grafana load models](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/)
- **Release comparison.** If the deployment supports a staged or canary rollout, compare the candidate with the baseline under equivalent traffic and configuration. Specify who observes it, what signals stop or roll it back, and how the team will tell a release regression from an unrelated incident. For migrations, verify that rollback can read the state written during rollout or document the tested recovery path. [Google SRE on canary releases](https://sre.google/workbook/canarying-releases/)

## 4. Tests, checks and release evidence

- **Unit and contract tests.** Cover changed invariants, boundary values, malformed requests, dependency failures and compatibility. Use independent expected values for monetary and statistical logic. A coverage percentage does not establish correctness.
- **Integration tests.** Exercise application registration, persistence, transaction rollback, failure propagation, queue coordination and resource-limit behavior on the normal execution path. Include an isolation or authorization regression when those boundaries change.
- **Data and numerical tests.** Use hand-computed fixtures, independent implementations where practical, and property or metamorphic checks with documented assumptions. Examples include truncating future bars, verifying fill chronology, checking accounting reconciliation and rerunning the same saved inputs. Compare timestamps, units and tolerance as well as headline returns.
- **Operational validation.** Check migration of representative old state, concurrent load, interruption/retry behavior, recovery and telemetry. For deployment changes record health checks, rollout/rollback criteria, compatibility during mixed versions and restore evidence where relevant.
- **Report what ran.** Include exact commands, exit codes, sample counts, baseline revision and any missing environment or data. Review skips and expected failures. A documentation change does not validate the code or establish that current deployment meets these standards.

From the repository root, switch to `backend/`. The project uses Python 3.12, `uv`, `uv.lock` and the local `.venv`. Select the appropriate existing checks for the change. The full suite and release checks apply according to the project and Studio release policy.

```bash
cd backend
uv lock --check
.venv/bin/python --version
.venv/bin/ruff check app main.py
.venv/bin/ruff format --check app main.py
.venv/bin/pyrefly check app
.venv/bin/python -m pytest -q tests/test_studio_v3_workspace.py
```

The test path is an example for workspace changes. Choose the tests that exercise the affected path. Use `uv sync --locked` when setting up the environment. [uv lock and sync](https://docs.astral.sh/uv/concepts/projects/sync/) For broader backend verification use the repository’s full backend test command and the dependency/unused-code audits listed in the [project plan](../../plans/PLAN.md). Prefer focused checks first. If a broad gate reports existing debt, keep its output and scope any fixes to the authorized work.

## 5. Detailed review checks by area

Use these checks when the file handles the named responsibility. In a full backend audit, cover every tracked backend file and record exclusions such as generated artifacts or vendored code. Review shared risks once at their ownership boundary and link the evidence from each affected file. For a focused change, review the changed path and its affected callers.

### 5.1 Readability, types and architecture

- [ ] Names express domain meaning. Prefer `fee_bps`, `price_usd` and `available_at` where the unit or timestamp changes interpretation. Follow existing naming, formatting and layout conventions.
- [ ] Public functions document side effects, preconditions, return and error contracts, mutation and ownership when they matter. Comments explain reasons and invariants. Remove stale comments when behavior changes.
- [ ] Represent domain values with appropriate types. Separate absence, zero, invalid, skipped and failed states. Make defaults explicit. Use validated objects across boundaries and check narrowing after untyped I/O. Keep type suppressions narrow and justified.
- [ ] Make control flow, lifecycle and state transitions easy to trace. Avoid mutable default arguments, hidden shared state and surprise import-time work. Pass dependencies explicitly where that makes behavior and ownership clearer.
- [ ] Keep transport and persistence details outside numerical kernels. Reuse the canonical implementation for shared semantics. Introduce an abstraction when it resolves measured duplication or a real interface need. Preserve callers when consolidating or deleting code.
- [ ] Keep code reviewable in small, coherent changes. Review changes in behavior, complexity, tests and documentation together. Follow the project formatter for routine style choices.

[PEP 8](https://peps.python.org/pep-0008/) · [PEP 257](https://peps.python.org/pep-0257/) · [Google code review guidance](https://google.github.io/eng-practices/review/reviewer/looking-for.html)

### 5.2 HTTP, events and interoperability

- [ ] Publish request, response and error contracts. Validate normalized values before expensive work. Test coercion, unknown fields, malformed payloads, size limits, time zones, numeric precision and JSON round trips.
- [ ] Preserve method semantics and response compatibility. Verify clients can distinguish invalid requests, missing data, conflicts, rate limiting, temporary unavailability and failed jobs. For background work, return a durable reference and document polling, expiry and terminal states.
- [ ] Document compatibility for optional fields, enum evolution, pagination and versioned stored objects. Use deterministic sorting and tie-breakers. Verify page boundaries under the documented consistency model.
- [ ] Declare cacheability and freshness for sensitive and public responses. Check private data isolation, representation variance, invalidation and conditional request behavior where applicable.
- [ ] For streaming, WebSockets and events, review reconnect, resume, replay, message ordering, duplicate handling and slow consumers. Put bounds on message size, buffering and connection lifetime. Apply authorization to subscriptions, replays and writes.

[HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html) · [HTTP caching](https://www.rfc-editor.org/rfc/rfc9111.html)

### 5.3 Security, privacy and abuse resistance

- [ ] Map principals, protected objects, trusted services and untrusted inputs. Verify object- and action-level authorization on normal, alternate and bulk routes. Test denied access with controlled fixtures. Check browser origin, CORS and CSRF rules against the authentication mechanism.
- [ ] Use established authentication and cryptography libraries. Define credential lifetime, rotation, revocation, storage and service scope. Use configurable secret references and redact credentials at every logging and error boundary.
- [ ] Parameterize database queries. Validate and allowlist external destinations where needed. Constrain filesystem roots, names and symlink handling, and bound archive expansion and decoded data. Keep subprocess arguments structured and controlled. Review deserialization and template evaluation as trust boundaries.
- [ ] Minimize personal and strategy data collection. Define purpose, access, retention, deletion and export behavior, including derived artifacts, caches, logs and backups. Distinguish product audit records from debugging telemetry.
- [ ] Apply layered resource limits and least privilege. Document what isolation provides in the deployed environment. Record authorization and sensitive administrative actions with attributable audit events and appropriate redaction.

[OWASP ASVS](https://asvs.owasp.org/) · [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

### 5.4 Data, storage and numerical correctness

- [ ] Document schema, invariants, indexes, canonical identifiers, publication/version rules and data ownership. Check behavior for old, partial, stale, corrupt, duplicated or out-of-order input. Preserve the last valid version when ingestion fails.
- [ ] Record transaction and consistency boundaries. Test two writers and reader visibility where relevant. Verify race-sensitive invariants in durable storage or a suitably synchronized owner. Check migrations with representative old data, interruption and restore.
- [ ] Audit financial timestamps, split/dividend conventions, benchmark comparability, annualization, slippage and fees, position limits and train/test boundaries. Track provenance and the availability of information, including revisions and delayed publications.
- [ ] Justify numeric representation and tolerances by units and use. Test empty, constant, extreme, near-zero and nonfinite values. Compare shape, ordering and missingness explicitly before applying numerical tolerances. Use exact checks for discrete counts, state transitions and canonical IDs.
- [ ] Check deterministic seeds, stable ordering, parallel reduction effects and any material environment dependence. Compare optimized paths with an independent oracle or hand-computed fixtures and retain a reproduction recipe.

[Studio research and engine standards](CODE_STANDARDS.md#2-quantitative-research-integrity) · [NumPy tolerance semantics](https://numpy.org/doc/stable/reference/generated/numpy.testing.assert_allclose.html)

### 5.5 Performance, resource lifecycle and cost

- [ ] Bound expensive dimensions before launch, including expanded work after joins, parameter products, decompression or fan-out. Budget concurrent per-job memory together with server, worker, cache and temporary disk usage.
- [ ] Inspect algorithm scaling, event-loop blocking, repeated I/O, temporary copies, serialization and model initialization. Profile with representative inputs before restructuring. Preserve correctness and measure the trade-off across wall time, CPU, memory and I/O.
- [ ] Define ownership and cleanup for descriptors, pools, connections, cursors, timers, tasks, child processes, temporary files, shared memory and GPU allocations where applicable. Verify limits and resource release after cancellation and failure.
- [ ] Evaluate saturation using the metrics in section 3. Track nonlinear cost increases from retries, duplicate work, outbound calls, hot keys, artifact retention and downstream rate limits. Where billed services apply, measure cost per successful workload and cap risky fan-out.
- [ ] For startup/runtime changes, record time to readiness, resident memory before and after first use, and the effect of worker replication. For native or accelerator paths, record actual thread counts, device utilization and memory transfers where they affect the decision.

### 5.6 Testing, debugging and evidence

- [ ] Use tests proportional to risk. Cover normal behavior, input boundaries, permissions, failures, concurrent execution, cancellation, retries and compatibility where relevant. Assert invariants and side effects as well as response values.
- [ ] Keep tests reproducible and isolated. Control time, randomness, filesystem, network and persistent state. Avoid unnecessary sleeps and reliance on test order. Investigate flaky tests and record any quarantine owner and exit criteria.
- [ ] Match the test layer to the claim. A unit test covers a function, a contract test covers a boundary, and an integration test covers wiring and side effects. Include adversarial data shapes and failure timing in approved defensive test environments when they matter.
- [ ] Track fixture provenance, license and sensitive contents. Explain updates to golden values with correctness evidence. Keep exact verification commands and exit codes. Use representative regression cases and record what could only be inferred from static inspection.

[pytest flaky-test guidance](https://docs.pytest.org/en/stable/explanation/flaky.html)

### 5.7 Configuration, delivery and recovery

- [ ] Validate configuration during startup or before use. Define environment precedence, safe defaults and what changes require a restart. Perform a clean install with the lockfile, check configuration compatibility, and keep secrets outside application artifacts.
- [ ] Review artifacts and dependencies. Check pinned versions, licenses, build inputs, provenance, known vulnerabilities and the expected production dependency set. Use available CI evidence. Record missing attestations or scanners as unverified when required for the release.
- [ ] Plan rollout and recovery for stateful or high-risk changes. Define readiness, graceful drain, job resumption, rollback criteria and when rollback itself could damage state. Validate backups by restoring them. Record acceptable data loss and recovery times where the service has those objectives.
- [ ] Give alerts an owner and a response. Distinguish symptoms from causes, test that important signals survive failures, and connect alerts to a related dashboard or recovery procedure. Audit high-impact operations and capture incident follow-ups with owners and dates.

[SLSA Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) · [Google SRE data integrity](https://sre.google/sre-book/data-integrity/)

## 6. Gates for a full backend audit

| Gate | What to produce |
|---|---|
| Inventory | Reviewed commit, tracked file inventory, ownership, file categories and any exclusions with reasons. |
| File evidence | A verdict record for each file reviewed, with caller and test references. Link shared evidence for system properties. |
| Risk register | Findings with severity, location, impacted users or data, reproducing evidence or missing evidence, owner and next step. Distinguish existing debt from changes under review. |
| System evidence | Representative workloads with resource measurements, correctness comparisons, failure cases and known limits. Include the deployment profile used to qualify each result. |
| Release decision | Applicable gates, unresolved blockers, accepted limitations with an owner and review date, rollout conditions and rollback/restore evidence where needed. |

A full audit can finish with known failures and blind spots if they are documented. Release readiness requires the applicable release gates to pass. Keep the findings in the review record and fix only work within the authorized scope.
