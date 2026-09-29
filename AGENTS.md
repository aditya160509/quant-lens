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
- State a minimal plan:
  - **Outcome:** the exact behavior requested
  - **Non-goal:** what this task will not do
  - **Files:** the smallest set expected to change
  - **Proof:** the check that will prove the change works
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

### If the plan grows

Stop when the work starts adding future-use layers, workaround stacks, unrelated cleanup, or tests for unstated behavior. Rewrite a smaller plan and confirm the new scope.

### Done means

- The requested behavior works and the acceptance criteria are met.
- Relevant checks pass, with the exact commands and results reported.
- Every touched file is necessary and the diff contains nothing unrelated.
- No debug code, backup copies, dead paths, or scratch files remain.
- Assumptions, limitations, and unverified runtime behavior are stated plainly.

## Editorial Standards for JFS/BIR Manuscript

### Absolute Rules
- **No em dashes (—)** — replace with commas, semicolons, colons, or restructure sentences
- **No raw underscore subscripts** in equations (e.g., `IAI_t` → `IAI_{t}` or proper rendered form)
- **Every equation must be numbered** sequentially (1), (2), (3)... and cross-referenced by number
- **Every Greek letter/symbol must be defined** in Notation Table near Section 4
- **Every acronym spelled out on first use**: IAI, GASI, AST, CSAD, AUC, FPR, DM, EM, AMM, ES95, FSI, CQL, DCV
- **Tables 1-N and Figures 1-N must be sequential** with no gaps, referenced in text before appearing
- **Abstract must be 150-250 words**

### Writing Style
- Tighten "which is" / "which was" / "that is" constructions — usually removable
- Active voice for findings ("we test," "we find"), not passive ("it is found that")
- Short declarative sentences for key claims; save complex sentences for nuance
- One idea per sentence, one point per paragraph
- Every section opens with one sentence stating what it does
- Transitions between sections — bridge "what we just showed" to "what comes next"
- Conclusion must synthesize, not restate abstract
- Consistent terminology throughout (pick "coordination regime" and use everywhere)
- Consistent number formatting in tables (3 decimals for coefficients, 4 for ratios)
- Lead with headline number, then support it
- Every statistical claim: number + test + plain-language meaning together

### Figure/Table Rules
- Every table/figure must be readable on its own (busy reader gets point from note alone)
- Table notes explain what's shown, not just cite source
- Captions specific enough to stand alone
- Order of presentation matches order of discussion
- No figure/table included without being referenced and discussed in text

### Submission Compliance
- Keywords: 4-6 matching journal convention
- JEL codes: verify current and match content
- DOI links on all references that have them
- Footnote numbering sequential, none orphaned
- Author contributions (CRediT), conflict of interest, funding statements present
- Highlights/graphical abstract if journal requires
