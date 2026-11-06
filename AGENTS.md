# Codex Project Notes

## Codebase Memory

This repo has been indexed with `codebase-memory-mcp`.

- Project name: `Users-adityabalaji-Downloads-quant-2`
- Root path: `/Users/adityabalaji/Downloads/quant  2`
- UI: `http://localhost:9749`
- Last observed graph size: `18,129` nodes / `63,414` edges
- Installed binary: `/Users/adityabalaji/.local/bin/codebase-memory-mcp`

Use it when asked about architecture, dependencies, impact analysis, dead code, duplicate code, request flow tracing, route/service relationships, or "the graph".

Useful commands:

```bash
/Users/adityabalaji/.local/bin/codebase-memory-mcp cli list_projects '{}'
/Users/adityabalaji/.local/bin/codebase-memory-mcp cli index_status '{"project":"Users-adityabalaji-Downloads-quant-2"}'
/Users/adityabalaji/.local/bin/codebase-memory-mcp cli get_architecture '{"project":"Users-adityabalaji-Downloads-quant-2","aspects":["all"]}'
/Users/adityabalaji/.local/bin/codebase-memory-mcp cli search_graph '{"project":"Users-adityabalaji-Downloads-quant-2","query":"portfolio risk service","limit":20}'
```

If the UI is not running:

```bash
/Users/adityabalaji/.local/bin/codebase-memory-mcp --ui=true --port=9749
```

Deletion/refactor rule: this workspace often has many uncommitted user changes. Before deleting anything, verify with the graph, `rg`, import/route registration checks, and preferably a backend/frontend smoke test. Do not delete files merely because they look isolated in the full graph.

## Scope Guard

Complete the current task with the minimum sufficient change.

### Before editing

- Read the relevant code, tests, and configuration directly. Do not work from search snippets or guesses.
- If the requirement is ambiguous or the premise is unverified, resolve that before building on it.
- Start with one implementation path. Split work only when the task has genuinely independent parts.

### While editing

- Reuse existing code, helpers, patterns, and test setup before adding anything new.
- Fix bugs at the root cause. Do not stack patches around a wrong premise.
- Add an abstraction, adapter, or config layer only for a second real caller in this task or a stated requirement.
- Preserve behavior outside the requested change.
- Do not design for rare or future cases nobody asked about.
- Remove code you replace. Keep an old path only when compatibility is an explicit requirement.

### Pause and confirm

Read-only discovery is always allowed. If the task has not already authorized it, get approval before:

- Materially expanding the scope or touching unrelated files.
- Adding a dependency, framework, service, or new test infrastructure.
- Changing a public API, schema, storage format, or wire format.
- Deleting or overwriting user data, discarding uncommitted work, rewriting history, or dropping data.
- Keeping two implementations of the same behavior alive.

### Testing

- Run the narrowest existing tests that exercise the changed behavior.
- Extend the most relevant existing test before creating a new test file.
- Add a test only when changed user-observable behavior is not covered, or when the user asks for one.
- Each new test must protect a clear acceptance criterion or regression risk.
- Do not backfill unrelated coverage or introduce test infrastructure for this task alone.
- Do not use passing tests as justification for extra abstractions or scope.


### Done means

- The requested behavior works and the acceptance criteria are met.
- Relevant checks pass, with the exact commands and results reported.
- Every touched file is necessary and the diff contains nothing unrelated.
- No debug code, backup copies, dead paths, or scratch files remain.
- Assumptions, limitations, and unverified runtime behavior are stated plainly.

"Cut taglines, helper text and secondary labels. If a screen needs them to make sense, fix the layout."

"Make the best decision that will elevate all three: the user experience (UX), developer experience (DX), and agent experience (AX) always, without breaking anything."