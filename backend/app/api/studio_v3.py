"""HTTP and MCP access to Studio v3. Every result is computed here; the browser never posts one back (PLAN §3.5)."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import difflib
import io
import json
import re
import time
import zipfile
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, ValidationError

from app.services.screener_v2.core.data_loader import BACKEND_DATA, normalize_symbol
from app.services.shared.formula import SignalError
from app.services.studio.jobs import JobStore
from app.services.studio_v3.core import (
    backtest,
    book,
    data,
    editor,
    formula,
    imports,
    limits,
    live,
    plain,
    pycode,
    qc_import,
    store,
    strategy_tests,
    templates,
    validate,
    workspace,
)
from app.services.studio_v3.core import compile as compiler
from app.services.studio_v3.core import (
    home as home_rules,
)
from app.services.studio_v3.core import library as lib
from app.services.studio_v3.core.spec import Settings, Strategy
from app.services.studio_v3.features.inputs import COST_PROFILES
from app.services.studio_v3.features.inputs import parse as parse_payload
from app.services.studio_v3.registry import feature_manifest, get_feature, run_feature

RESULTS_DIR = BACKEND_DATA / "studio_v3" / "results"
JOBS = JobStore(path=BACKEND_DATA / "studio_v3" / "jobs.json")

router = APIRouter(prefix="/studio-v3")


class FeatureRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class SpecRequest(BaseModel):
    spec: dict[str, Any]
    folder: str = ""


def _actor(header: str | None) -> str:
    """human, ai_helper or agent:<name>. Anything else is treated as an agent, never silently as a human."""
    a = (header or "human").strip().lower()
    return a if a in {"human", "ai_helper"} or a.startswith("agent") else f"agent:{a}"


def _spec(raw: dict[str, Any]) -> Strategy:
    try:
        return Strategy(**raw)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc


# --- manifest, limits, bars ----------------------------------------------------


@router.get("/manifest")
@router.get("/features")
def manifest() -> dict[str, Any]:
    return {"features": feature_manifest(), "cost_profiles": COST_PROFILES, "formula": formula.catalogue()}


@router.get("/limits")
def get_limits() -> dict[str, Any]:
    a = limits.audit()
    return {"freshness": limits.freshness(), "data": {k: v for k, v in a.items() if k != "by_year"}}


@router.get("/data-audit")
def data_audit() -> dict[str, Any]:
    return {"freshness": limits.freshness(), **limits.audit()}


_RULE = {"1w": "W-FRI", "1mo": "ME"}


@router.get("/bars")
def bars(symbols: str, tf: str = "1d", start: str | None = Query(None, alias="from"), end: str | None = Query(None, alias="to")) -> dict[str, Any]:
    """The one price source for every page: daily bars, 1h where held, weekly and monthly resampled."""
    names = [normalize_symbol(s) for s in symbols.replace(",", " ").split() if s][:8]
    if tf not in {"1d", "1w", "1mo"} or not names:
        raise HTTPException(422, "tf must be 1d, 1w or 1mo, with at least one symbol")
    out: dict[str, Any] = {}
    p = data.panel(names, start, end)
    for i, s in enumerate(p.symbols):
        df = pd.DataFrame({f: getattr(p, f)[:, i] for f in data.FIELDS}, index=p.dates).dropna(subset=["close"])
        if tf in _RULE:
            df = df.resample(_RULE[tf]).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["close"])
        out[s] = [{"time": str(d.date()), "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": 0.0 if np.isnan(r.volume) else r.volume} for d, r in zip(df.index, df.itertuples(), strict=True)]
    return {"tf": tf, "bars": out, "missing": [s for s in names if s not in out]}


# --- compile and strategies ------------------------------------------------------


@router.post("/compile")
def compile_strategy(request: SpecRequest) -> dict[str, Any]:
    t0 = time.perf_counter()
    out = compiler.compile_spec(_spec(request.spec))
    return {**out, "ms": round((time.perf_counter() - t0) * 1000, 2)}


class PlainRequest(BaseModel):
    text: str


@router.post("/plain-english")
def plain_english(request: PlainRequest) -> dict[str, Any]:
    """Sentence -> rule fields for review; nothing is saved or run."""
    try:
        return plain.to_spec(request.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/to-python")
def to_python(request: SpecRequest) -> dict[str, str]:
    """Formula -> Python, one way (the formulas stay); a blank spec gets the starter."""
    spec = _spec(request.spec)
    return {"code": pycode.from_formulas(spec) if spec.entry_long.strip() or spec.entry_short.strip() else pycode.TEMPLATE}


class CodeRequest(BaseModel):
    code: str


@router.post("/format-python")
def format_python(request: CodeRequest) -> dict[str, str]:
    """ruff format; code that does not parse comes back unchanged."""
    import subprocess
    import sys
    from pathlib import Path

    ruff = Path(sys.executable).with_name("ruff")
    p = subprocess.run([str(ruff), "format", "--line-length", "110", "-"], check=False, input=request.code, capture_output=True, text=True, timeout=10)
    return {"code": p.stdout if p.returncode == 0 and p.stdout else request.code}


class BuildProjectDocument(BaseModel):
    code: str = Field(max_length=200_000)
    file: str = Field(default="main.py", max_length=128)
    files: dict[str, str] = Field(default_factory=dict, max_length=50)


def _editor_project(request: BuildProjectDocument) -> Strategy:
    sources = {**request.files, request.file: request.code}
    main = sources.pop("main.py", "")
    if not request.file.endswith(".py"):
        raise HTTPException(422, "Select a Python file.")
    return _spec({"code": main, "files": sources})


class BuildTestRequest(BaseModel):
    code: str = Field(default="", max_length=200_000)  # main.py
    files: dict[str, str] = Field(default_factory=dict, max_length=50)
    file: str | None = Field(default=None, max_length=128)  # run one test file
    name: str | None = Field(default=None, max_length=128)  # run one test


@router.post("/build/test")
def run_strategy_tests(request: BuildTestRequest) -> dict[str, Any]:
    """Runs def test_* from the project's test_*.py files in the sandbox child; `from studio.testing import bars` is the fixture."""
    return strategy_tests.run({**request.files, "main.py": request.code}, request.file, request.name)


class BuildCheckRequest(BuildProjectDocument):
    params: dict[str, float] = Field(default_factory=dict)
    strictness: Literal["basic", "strict"] = "basic"  # strict adds unused imports and the studio-api header
    severity: dict[str, Literal["error", "warning", "info", "off"]] = Field(default_factory=dict)  # per problem code


class BuildProblem(BaseModel):
    severity: str
    file: str = "main.py"
    line: int
    column: int
    end_column: int
    code: str
    message: str
    fix: dict[str, Any] | None = None  # {title, edits[{line, column, end_line, end_column, text}]}


class BuildCheckResult(BaseModel):
    problems: list[BuildProblem]


@router.post("/build/check", response_model=BuildCheckResult)
def check_python(request: BuildCheckRequest) -> BuildCheckResult:
    project = _editor_project(request)
    modules = {name[:-3] for name in project.files if name.endswith(".py")}
    return BuildCheckResult(problems=pycode.lint(request.code, request.params, file=request.file, modules=modules, strictness=request.strictness, severity=request.severity))


@router.post("/build/typecheck", response_model=BuildCheckResult)
def typecheck_python(request: BuildCheckRequest) -> BuildCheckResult:
    """Type errors from ty over the project files (B-33). Names the linter already reports are left to it."""
    project = _editor_project(request)
    return BuildCheckResult(problems=pycode.typecheck({"main.py": project.code, **project.files}, request.file))


class BuildCompleteRequest(BaseModel):
    scope: str = Field(max_length=40)
    code: str = Field(default="", max_length=200_000)
    prefix: str = Field(default="", max_length=100)
    params: list[str] = Field(default_factory=list, max_length=1000)
    symbols: list[str] = Field(default_factory=list, max_length=5000)


class BuildMember(BaseModel):
    name: str
    kind: str
    signature: str | None
    documentation: str | None
    insert_text: str | None = None


class BuildSignatureRequest(BuildCompleteRequest):
    name: str = Field(min_length=1, max_length=100)


@router.post("/build/complete", response_model=list[BuildMember])
def complete_python(request: BuildCompleteRequest) -> list[dict]:
    return pycode.editor_members(request.scope, request.code, request.prefix, params=request.params, symbols=request.symbols)


@router.post("/build/signature", response_model=BuildMember | None)
def signature_python(request: BuildSignatureRequest) -> dict | None:
    return next((item for item in pycode.editor_members(request.scope, request.code, request.name)
                 if item["name"] == request.name and item["signature"]), None)


class BuildDefinitionRequest(BuildProjectDocument):
    line: int = Field(ge=1)
    column: int = Field(ge=1)


class BuildDefinition(BaseModel):
    file: str
    name: str
    line: int
    column: int


def _navigate_python(request: BuildDefinitionRequest, *, references=False, new_name=None):
    project = _editor_project(request)
    try:
        return pycode.navigate(request.code, request.line, request.column, file=request.file,
                               files=project.project_files(), references=references, new_name=new_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/build/definition", response_model=list[BuildDefinition])
def define_python(request: BuildDefinitionRequest):
    return _navigate_python(request)


@router.post("/build/references", response_model=list[BuildDefinition])
def reference_python(request: BuildDefinitionRequest):
    return _navigate_python(request, references=True)


class BuildRenameRequest(BuildDefinitionRequest):
    new_name: str = Field(min_length=1, max_length=100)


@router.post("/build/rename", response_model=dict[str, str])
def rename_python(request: BuildRenameRequest):
    return _navigate_python(request, new_name=request.new_name)


class BuildOutlineRequest(BaseModel):
    code: str = Field(max_length=200_000)


class BuildSymbol(BaseModel):
    name: str
    kind: Literal["class", "method", "function", "indicator"]
    line: int
    column: int
    end_line: int
    end_column: int
    children: list[BuildSymbol]


@router.post("/build/outline", response_model=list[BuildSymbol])
def outline_python(request: BuildOutlineRequest) -> list[dict]:
    return pycode.outline(request.code)


class BuildChecksRequest(BaseModel):
    spec: dict[str, Any]
    settings: Settings | None = None


class BuildDataUse(BaseModel):
    role: str
    fields: list[str]
    windows: list[int]


class BuildChecksResult(BaseModel):
    warmup_bars: int
    warmup_share: float | None = None
    warnings: list[str] = Field(default_factory=list)
    first_eligible_date: str | None
    data_used: list[BuildDataUse]
    period: list[str]
    universe: dict[str, Any]
    survivorship: dict[str, Any]
    parameters: dict[str, float]


@router.post("/build/checks", response_model=BuildChecksResult)
def build_checks(request: BuildChecksRequest) -> dict[str, Any]:
    """Warm-up bars, the data each rule reads and survivorship exposure for the Build checks card (B-119)."""
    try:
        return backtest.checks(_spec(request.spec), request.settings or Settings(symbols=[], benchmark="SPY"))
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc


class QuantConnectImportRequest(BaseModel):
    source: str = Field(min_length=1, max_length=400_000)


class QuantConnectRewrite(BaseModel):
    line: int
    before: str
    after: str
    reason: str | None = None


class QuantConnectLeftover(BaseModel):
    line: int
    source: str
    reason: str


class QuantConnectImportResult(BaseModel):
    ok: bool
    code: str
    symbols: list[str]
    settings: dict[str, Any]
    warmup: int | None = None
    converted: list[QuantConnectRewrite]
    unconverted: list[QuantConnectLeftover]
    problems: list[BuildProblem]


@router.post("/build/import-quantconnect", response_model=QuantConnectImportResult)
def import_quantconnect(request: QuantConnectImportRequest) -> dict[str, Any]:
    """Keep the user's QuantConnect algorithm, rewrite the calls Studio can run, list every line left behind (B-163)."""
    return qc_import.convert(request.source)


class PreviewRequest(BaseModel):
    spec: dict
    symbol: str = "SPY"
    symbols: list[str] | None = Field(default=None, max_length=50)  # default: Strategy.universe, else `symbol`
    years: float = Field(default=2.0, ge=0.5, le=10)
    repaint: bool = True  # False: skip the look-ahead replay for a fast typing preview


class ConditionRequest(PreviewRequest):
    expression: str = Field(min_length=1, max_length=8192)


class ConditionResult(BaseModel):
    symbol: str
    observations: int
    true_count: int
    true_rate: float | None
    last_true_date: str | None
    fired_dates: list[str]
    constant: bool | None


def _condition_stats(expression: str, params: dict[str, float], symbol: str) -> ConditionResult:
    try:
        formula.parse(expression, params)
        prepared = backtest.prepare(Settings(symbols=[symbol], benchmark=""))
        panel = prepared.panel
        dates = panel.dates
        values = formula.evaluate(expression, prepared.sig_bars, dates, params)[:, 0]
    except SignalError as exc:
        raise HTTPException(422, {"message": exc.message, "start": exc.start, "end": exc.end,
                                  "hint": "Correct the condition before inspecting it."}) from exc
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc

    visible = dates >= dates[-1] - pd.DateOffset(days=730)
    observed = visible & np.isfinite(panel.close[:, 0]) & np.isfinite(values)
    fired = observed & (values > 0)
    fired_dates = dates[fired].strftime("%Y-%m-%d").tolist()
    count, observations = len(fired_dates), int(observed.sum())
    return ConditionResult(
        symbol=panel.symbols[0], observations=observations, true_count=count,
        true_rate=count / observations if observations else None,
        last_true_date=fired_dates[-1] if fired_dates else None, fired_dates=fired_dates,
        constant=(count == observations) if observations and count in (0, observations) else None,
    )


@router.post("/build/condition", response_model=ConditionResult)
def inspect_condition(request: ConditionRequest) -> ConditionResult:
    return _condition_stats(request.expression, _spec(request.spec).values(), request.symbol)


class EditorPosition(BaseModel):
    code: str = Field(max_length=200_000)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)  # name -> {value, min, max, step}
    last_values: dict[str, float] = Field(default_factory=dict)  # formula text -> value from the last preview


class HoverResult(BaseModel):
    contents: str
    lookback_bars: int | None
    last_value: float | None
    range: dict[str, int]


@router.post("/build/hover", response_model=HoverResult | None)
def hover_python(request: EditorPosition) -> dict | None:
    """Markdown docs for the symbol at the cursor, with lookback bars for a formula and the parameter range for a parameter."""
    return editor.hover(request.code, request.line, request.column, request.params, request.last_values)


class InlayRequest(BaseModel):
    code: str = Field(max_length=200_000)
    params: dict[str, float] = Field(default_factory=dict)
    last_values: dict[str, float] = Field(default_factory=dict)


@router.post("/build/inlay-hints")
def inlay_python(request: InlayRequest) -> list[dict[str, Any]]:
    return editor.inlay_hints(request.code, request.params, request.last_values)


class LensRequest(BaseModel):
    code: str = Field(max_length=200_000)
    symbol: str = "SPY"
    params: dict[str, float] = Field(default_factory=dict)
    debug_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.post("/build/codelens")
def codelens_python(request: LensRequest) -> list[dict[str, Any]]:
    """Run and debug lenses above on_bar and on_data, and the true-rate of each literal ctx.rule on the symbol's last 2 years."""
    symbol = normalize_symbol(request.symbol)
    rates = {}
    for _, expression in editor.formula_literals(request.code):
        try:
            rates[expression] = _condition_stats(expression, request.params, symbol).model_dump()
        except HTTPException:
            continue  # a rule that does not parse is lint's job
    return editor.code_lens(request.code, symbol, rates, request.debug_from)


class CodeActionRequest(BaseModel):
    code: str = Field(max_length=200_000)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    end_line: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)


@router.post("/build/code-actions")
def code_actions_python(request: CodeActionRequest) -> list[dict[str, Any]]:
    return editor.code_actions(request.code, request.line, request.column, request.end_line, request.end_column)


@router.post("/build/organise-imports")
def organise_imports_python(request: CodeRequest) -> dict[str, str]:
    return {"code": editor.organise_imports(request.code)}


class FormatRangeRequest(CodeRequest):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


@router.post("/build/format-range")
def format_range_python(request: FormatRangeRequest) -> dict[str, str]:
    return {"code": editor.format_range(request.code, request.start_line, request.end_line)}


@router.post("/build/migrate")
def migrate_python(request: CodeRequest) -> dict[str, Any]:
    """Bring code to the current `# studio-api` version; returns the new code and what changed."""
    return editor.migrate(request.code)


class PreviewLog(BaseModel):
    date: str
    symbol: str | None
    line: int
    text: str
    level: str
    fields: dict[str, Any] | None = None


class PreviewPlotPoint(BaseModel):
    date: str
    symbol: str | None
    value: float | None


class StrategyFrame(BaseModel):
    file: str
    line: int
    column: int
    function: str


class StrategyProblem(BaseModel):
    file: str | None = None
    line: int | None = None
    column: int | None = None
    exception_type: str | None = None
    traceback: list[StrategyFrame] | None = None
    locals: dict[str, Any] | None = None  # at the failing bar: symbol, date, bar_index, variables of the failing frame, self attributes (state)


class PreviewWarmup(BaseModel):
    inferred_bars: int | None = None  # longest window the rules need; the first date with every value is inferred_start_date
    inferred_start_date: str | None = None
    bars: int
    first_eligible_date: str | None
    first_eligible_by_symbol: dict[str, str | None]


class PreviewMark(BaseModel):
    date: str
    symbol: str
    label: str


class PreviewTableRow(BaseModel):
    date: str
    symbol: str | None
    cells: dict[str, str | bool | int | float | None]


class PreviewResult(BaseModel):
    status: str
    reason: str | None = None
    line: int | None = None
    problem: StrategyProblem | None = None
    symbol: str | None = None
    symbols: list[str] | None = None
    bars_by_symbol: dict[str, list[dict[str, Any]]] | None = None
    window: dict[str, str] | None = None
    bars: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    total_return: float | None = None
    repaint: dict[str, Any] | None = None
    logs: list[PreviewLog] | None = None
    plots: dict[str, list[PreviewPlotPoint]] | None = None
    plot_charts: dict[str, str] | None = None
    draw: dict | None = None
    marks: list[PreviewMark] | None = None
    tables: dict[str, list[PreviewTableRow]] | None = None
    warmup: PreviewWarmup | None = None
    risk_events: list[dict[str, Any]] | None = None
    settings_overrides: dict[str, Any] | None = None
    order_lines: list[dict[str, Any]] | None = None  # {file, line, count, dates[<=5]}: strategy lines that placed orders
    profile: dict[str, Any] | None = None  # only from POST /build/profile
    invariants: dict[str, Any] | None = None  # {count, rows[{date, symbol, file, line, text}]}; present only when an assert_invariant failed


class DebugBreakpointRequest(BaseModel):
    file: str = Field(default="main.py", max_length=128)
    line: int = Field(ge=1)
    condition: str | None = Field(default=None, max_length=500)


class BuildDebugRequest(PreviewRequest):
    date: dt.date
    step: Literal[-1, 0, 1] = 0
    event: Literal["order", "fill", "equity"] | None = None
    loss_fraction: float | None = Field(default=None, gt=0, le=1)
    breakpoint: DebugBreakpointRequest | None = None
    step_line: bool = False  # with `breakpoint` naming the paused line: stop at the next executed line on the same bar (F11)
    settings: Settings | None = None


class WatchRequest(PreviewRequest):
    date: dt.date
    expressions: list[str] = Field(min_length=1, max_length=20)
    history: int = Field(default=20, ge=1, le=500)


@router.post("/build/watch")
def watch_expressions(request: WatchRequest) -> list[dict[str, Any]]:
    """Formula watches at a paused bar with their recent history. A formula that does not parse comes back on its own row with an error."""
    try:
        return backtest.watch(_spec(request.spec), normalize_symbol(request.symbol), request.date.isoformat(), request.expressions, request.history)
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc


class DebugOrder(BaseModel):
    symbol: str
    quantity_or_direction: float
    exit_side: int
    limit: float | None
    stop: float | None
    canceled: bool


class DebugFill(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float


class DebugBreakpointHit(BaseModel):
    file: str
    line: int
    hit_count: int
    locals: dict[str, Any]


class BuildDebugResult(BaseModel):
    date: str
    symbol: str
    bar_index: int
    state: dict[str, Any]
    context: dict[str, float | None]
    orders: list[DebugOrder]
    fills: list[DebugFill]
    previous_date: str | None
    next_date: str | None
    breakpoint: DebugBreakpointHit | None = None
    equity_change: float | None = None


@router.post("/build/debug", response_model=BuildDebugResult, response_model_exclude_unset=True)
def debug_python(request: BuildDebugRequest) -> dict:
    symbol = normalize_symbol(request.symbol)
    settings = request.settings or Settings(symbols=[symbol], benchmark="")
    if request.step_line and (not request.breakpoint or request.step or request.event):
        raise HTTPException(422, "Step a line from a paused file and line: send `breakpoint` with step_line and no step or event.")
    if sum(bool(item) for item in (request.step, request.event, request.breakpoint)) > 1:
        raise HTTPException(422, "Choose a session step, event jump or breakpoint.")
    if (request.event == "equity") != (request.loss_fraction is not None):
        raise HTTPException(422, "Set loss_fraction only for an equity event.")
    spec = _spec(request.spec)
    breakpoint = None
    if request.breakpoint:
        source = spec.project_files().get(request.breakpoint.file)
        if source is None or not request.breakpoint.file.endswith(".py") or request.breakpoint.line > len(source.splitlines()):
            raise HTTPException(422, "Choose an existing line in a Python project file.")
        try:
            condition = pycode.breakpoint_condition(request.breakpoint.condition)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        breakpoint = {"file": request.breakpoint.file, "line": request.breakpoint.line, "condition": condition, "step": request.step_line}
    try:
        return backtest.debug_bar(spec, settings, symbol, request.date.isoformat(), request.step,
                                  "breakpoint" if breakpoint else request.event, breakpoint, request.loss_fraction)
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc
    except pycode.CodeError as exc:
        raise HTTPException(422, {"message": exc.message, **exc.problem}) from exc


@router.post("/preview", response_model=PreviewResult, response_model_exclude_unset=True)
def preview(request: PreviewRequest) -> dict[str, Any]:
    try:
        return backtest.preview(_spec(request.spec), request.symbol, request.years, symbols=[normalize_symbol(s) for s in request.symbols] if request.symbols else None, repaint=request.repaint)
    except backtest.Refusal as exc:
        return {"status": "skipped", "reason": exc.reason, "bars": [], "trades": []}
    except pycode.CodeError as exc:
        return {"status": "error", "reason": exc.message, "line": exc.line, "problem": exc.problem, "bars": [], "trades": []}


@router.post("/build/profile", response_model=PreviewResult, response_model_exclude_unset=True)
def profile_python(request: PreviewRequest) -> dict[str, Any]:
    """The preview run with the profiler on: `profile.lines` are the 10 slowest strategy lines and `profile.functions` the time per function. Slower than a preview."""
    try:
        return backtest.preview(_spec(request.spec), request.symbol, request.years, symbols=[normalize_symbol(s) for s in request.symbols] if request.symbols else None, profile=True)
    except backtest.Refusal as exc:
        return {"status": "skipped", "reason": exc.reason, "bars": [], "trades": []}
    except pycode.CodeError as exc:
        return {"status": "error", "reason": exc.message, "line": exc.line, "problem": exc.problem, "bars": [], "trades": []}


@router.get("/strategies/{sid}/holdout")
def holdout_log(sid: str) -> dict[str, Any]:
    _known(store.get, sid)
    return {"looks": validate.holdout_looks(sid), "agent_budget": validate.HOLDOUT_AGENT_BUDGET}


class FreezeRequest(BaseModel):
    version: int | None = None
    as_of: str | None = None


@router.post("/strategies/{sid}/freeze")
def freeze_paper(sid: str, request: FreezeRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Freeze a version to paper. Agents cannot freeze: it needs a human click (PAGES §10.5)."""
    actor = _actor(x_studio_actor)
    if actor.startswith("agent"):
        raise HTTPException(403, "Freezing to paper needs a human click")
    s = _known(store.get, sid, request.version)
    return live.freeze(sid, s["version"], request.as_of, actor)


class ChannelsRequest(BaseModel):
    urls: list[str]
    quiet: str = ""


@router.put("/strategies/{sid}/channels")
def put_channels(sid: str, request: ChannelsRequest) -> dict[str, Any]:
    _known(store.get, sid)
    return {"channels": [{"kind": c["url"].split("://")[0], "quiet": c["quiet"]} for c in live.set_channels(sid, request.urls, request.quiet)]}


@router.post("/strategies/{sid}/test-alert")
def test_alert(sid: str) -> dict[str, Any]:
    _known(store.get, sid)
    return {"sent": live.deliver(sid, "Studio test alert", "This is a test alert from Studio.")}


@router.get("/templates/stats")
def template_stats() -> dict[str, Any]:
    """Each starter's backtest on its default universe; "computing" until the background pass finishes."""
    return templates.stats()


@router.get("/templates")
def get_templates() -> dict[str, Any]:
    return {"templates": templates.list_templates(), "python_templates": templates.list_python_templates()}


@router.get("/strategies")
def list_strategies(archived: bool = False) -> dict[str, Any]:
    return {"strategies": store.list_strategies(archived)}


@router.post("/strategies")
def create_strategy(request: SpecRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    return store.create(_spec(request.spec), _actor(x_studio_actor), request.folder)


@router.post("/strategies/import")
def import_strategy(request: SpecRequest, save: bool = False, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Recompile an imported JSON spec and show the findings before anything is saved (H-4)."""
    spec = _spec(request.spec)
    found = compiler.compile_spec(spec)
    saved = store.create(spec, _actor(x_studio_actor), request.folder) if save and found["ok"] else None
    return {"compile": found, "spec": spec.model_dump(), "saved": saved}


def _known(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc


def _guarded(fn, *args, **kwargs):
    """Workspace calls: a refusal becomes a 4xx whose detail names the fix; an unknown id a 404."""
    try:
        return fn(*args, **kwargs)
    except workspace.Refused as exc:
        raise HTTPException(exc.status, {"message": str(exc), **exc.extra}) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc


@router.get("/strategies/{sid}")
def get_strategy(sid: str, version: int | None = None) -> dict[str, Any]:
    return _known(store.get, sid, version)


@router.put("/strategies/{sid}")
def save_version(sid: str, request: SpecRequest, x_studio_actor: str | None = Header(None), x_studio_session: str | None = Header(None)) -> dict[str, Any]:
    _guarded(workspace.check_writer, sid, x_studio_session)
    try:
        return _known(store.save_version, sid, _spec(request.spec), _actor(x_studio_actor))
    except store.VersionLocked as exc:
        raise HTTPException(423, str(exc)) from exc


class ProjectFileUpdate(BaseModel):
    operation: Literal["create", "save", "rename", "delete"]
    name: str = Field(min_length=1, max_length=128)
    source: str | None = Field(default=None, max_length=200_000)
    new_name: str | None = Field(default=None, max_length=128)
    base_version: int = Field(ge=1)


@router.get("/strategies/{sid}/files")
def get_project_files(sid: str, version: int | None = None, base_version: int | None = None) -> dict[str, Any]:
    saved = _known(store.get, sid, version)
    files = _spec(saved["spec"]).project_files()
    result: dict[str, Any] = {"version": saved["version"], "files": files}
    if base_version is not None:
        base = _spec(_known(store.get, sid, base_version)["spec"]).project_files()
        result["diffs"] = {
            name: "".join(difflib.unified_diff(base.get(name, "").splitlines(keepends=True), files.get(name, "").splitlines(keepends=True),
                                               fromfile=name if name in base else "/dev/null", tofile=name if name in files else "/dev/null"))
            for name in sorted(set(base) | set(files)) if base.get(name) != files.get(name)
        }
    return result


@router.patch("/strategies/{sid}/files")
def update_project_file(sid: str, request: ProjectFileUpdate, x_studio_actor: str | None = Header(None), x_studio_session: str | None = Header(None)) -> dict[str, Any]:
    _guarded(workspace.check_writer, sid, x_studio_session)
    saved = _known(store.get, sid)
    if saved["version"] != request.base_version:
        raise HTTPException(409, f"Strategy is at version {saved['version']}. Reload before saving.")
    spec = _spec(saved["spec"])
    files = spec.project_files()
    name, operation = request.name, request.operation
    if operation == "create":
        if name in files:
            raise HTTPException(409, "That filename already exists.")
        files[name] = request.source or ""
    elif name not in files:
        raise HTTPException(404, "File not found.")
    elif operation == "save":
        if request.source is None:
            raise HTTPException(422, "Include source to save this file.")
        files[name] = request.source
    elif name == "main.py":
        raise HTTPException(422, "main.py is the project entry point.")
    elif operation == "delete":
        del files[name]
    else:
        new_name = request.new_name
        if not new_name:
            raise HTTPException(422, "Provide a new filename.")
        if new_name in files:
            raise HTTPException(409, "That filename already exists.")
        files[new_name] = files.pop(name)
    code = files.pop("main.py")
    if len(code.encode("utf-8")) > 200_000:
        raise HTTPException(422, "main.py exceeds 200 KB.")
    updated = _spec({**spec.model_dump(), "code": code, "files": files})
    try:
        versioned = _known(store.save_version, sid, updated, _actor(x_studio_actor), base_version=request.base_version)
    except store.VersionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except store.VersionLocked as exc:
        raise HTTPException(423, str(exc)) from exc
    return {"version": versioned["version"], "files": _spec(versioned["spec"]).project_files()}


@router.post("/strategies/{sid}/versions/{version}/restore")
def restore_version(sid: str, version: int, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Copy an old version to a new latest one; nothing is deleted."""
    return _known(store.restore, sid, version, _actor(x_studio_actor))


@router.post("/strategies/{sid}/versions/{version}/branch")
def branch_version(sid: str, version: int, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Start a new strategy from an old version."""
    return _known(store.branch, sid, version, _actor(x_studio_actor))


@router.get("/strategies/{sid}/blame")
def blame_file(sid: str, file: str = "main.py") -> list[dict[str, Any]]:
    """Each line of the latest file with the version that last changed it."""
    return _known(store.blame, sid, file)


class VersionLabel(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = Field(default=None, max_length=10)


class VersionLock(BaseModel):
    version: int | None = Field(default=None, ge=1)  # null unlocks


@router.get("/strategies/{sid}/timeline")
def version_timeline(sid: str) -> list[dict[str, Any]]:
    """Every version with its name, tags, lock state and latest backtest summary."""
    return _guarded(workspace.timeline, sid)


@router.put("/strategies/{sid}/versions/{version}/label")
def label_version(sid: str, version: int, request: VersionLabel) -> dict[str, Any]:
    return _guarded(workspace.label_version, sid, version, request.name, request.tags)


@router.put("/strategies/{sid}/lock")
def lock_version(sid: str, request: VersionLock) -> dict[str, Any]:
    """Lock the live version: saving over it answers 423 until it is unlocked."""
    return _guarded(workspace.set_lock, sid, request.version)


class MergeRequest(BaseModel):
    source: str
    resolution: Literal["ours", "theirs"] | None = None


@router.get("/strategies/{sid}/compare/{other}")
def compare_strategies(sid: str, other: str) -> dict[str, Any]:
    """File diffs and latest run summaries of two strategies, for comparing branches."""
    return _guarded(workspace.compare, sid, other)


@router.post("/strategies/{sid}/merge")
def merge_branch(sid: str, request: MergeRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Merge a branch back into the strategy it was branched from; 409 lists conflicting files."""
    return _guarded(workspace.merge, sid, request.source, request.resolution, _actor(x_studio_actor))


@router.get("/strategies/{sid}/history")
def local_history(sid: str) -> list[dict[str, Any]]:
    """Autosave snapshots from the last 7 days, newest first."""
    _known(store.get, sid)
    return workspace.history(sid)


class CommentBody(BaseModel):
    file: str = Field(default="main.py", max_length=120)
    line: int = Field(default=1, ge=1, le=100_000)
    text: str = Field(min_length=1, max_length=4000)
    author: str = Field(default="you", max_length=60)
    thread_id: str | None = Field(default=None, max_length=16)


@router.get("/strategies/{sid}/comments")
def list_comments(sid: str) -> list[dict[str, Any]]:
    """Line comment threads, oldest first; a reply shares its thread's file and line."""
    _known(store.get, sid)
    return workspace.comments(sid)


@router.post("/strategies/{sid}/comments")
def add_comment(sid: str, request: CommentBody) -> dict[str, Any]:
    return _guarded(workspace.add_comment, sid, **request.model_dump())


@router.delete("/strategies/{sid}/comments/{comment_id}")
def remove_comment(sid: str, comment_id: str) -> dict[str, bool]:
    _guarded(workspace.delete_comment, sid, comment_id)
    return {"deleted": True}


class SnippetBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    prefix: str = Field(min_length=1, max_length=32)
    body: str = Field(max_length=20_000)
    description: str = Field(default="", max_length=300)


@router.get("/snippets")
def list_snippets() -> list[dict[str, Any]]:
    return workspace.snippets()


@router.post("/snippets")
def add_snippet(request: SnippetBody) -> dict[str, Any]:
    return _guarded(workspace.save_snippet, **request.model_dump())


@router.put("/snippets/{snippet_id}")
def update_snippet(snippet_id: str, request: SnippetBody) -> dict[str, Any]:
    return _guarded(workspace.save_snippet, **request.model_dump(), snippet_id=snippet_id)


@router.delete("/snippets/{snippet_id}")
def remove_snippet(snippet_id: str) -> dict[str, bool]:
    _guarded(workspace.delete_snippet, snippet_id)
    return {"deleted": True}


@router.post("/strategies/{sid}/share")
def share_strategy(sid: str, version: int | None = None) -> dict[str, Any]:
    """A read-only link to one version; anyone with the token can read or fork it."""
    return _guarded(workspace.share, sid, version)


@router.get("/share/{token}")
def read_shared(token: str) -> dict[str, Any]:
    return _guarded(workspace.read_share, token)


@router.post("/share/{token}/fork")
def fork_shared(token: str, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    return _guarded(workspace.fork_share, token, _actor(x_studio_actor))


@router.delete("/share/{token}")
def revoke_shared(token: str) -> dict[str, bool]:
    _guarded(workspace.revoke_share, token)
    return {"revoked": True}


class LeaseRequest(BaseModel):
    session: str = Field(min_length=1, max_length=64)
    take_over: bool = False


@router.post("/strategies/{sid}/lease")
def acquire_lease(sid: str, request: LeaseRequest) -> dict[str, Any]:
    """Take or renew the single editing session (60 s; renew while the editor is open). 409 names the holder."""
    return _guarded(workspace.acquire_lease, sid, request.session, request.take_over)


@router.delete("/strategies/{sid}/lease")
def release_lease(sid: str, session: str) -> dict[str, bool]:
    _guarded(workspace.release_lease, sid, session)
    return {"released": True}


class FindReplaceRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    replacement: str | None = Field(default=None, max_length=2000)  # omit to preview matches only
    regex: bool = False
    match_case: bool = False
    whole_word: bool = False
    base_version: int | None = Field(default=None, ge=1)


@router.post("/strategies/{sid}/find-replace")
def find_replace(sid: str, request: FindReplaceRequest, x_studio_actor: str | None = Header(None), x_studio_session: str | None = Header(None)) -> dict[str, Any]:
    """Project-wide matches with line and column; with a replacement it saves one new version."""
    if request.replacement is not None:
        _guarded(workspace.check_writer, sid, x_studio_session)
    try:
        return _guarded(workspace.find_replace, sid, request.query, request.replacement, regex=request.regex, match_case=request.match_case,
                        whole_word=request.whole_word, base_version=request.base_version, actor=_actor(x_studio_actor))
    except store.VersionLocked as exc:
        raise HTTPException(423, str(exc)) from exc


@router.get("/strategies/{sid}/export.zip")
def export_project_zip(sid: str, version: int | None = None) -> Response:
    return Response(_guarded(workspace.export_zip, sid, version), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{sid}.zip"'})


@router.post("/strategies/import-zip")
async def import_project_zip(request: Request, name: str | None = None, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Body is the zip itself (Content-Type application/zip): main.py plus helpers at the top level, 50 files, 200 KB each."""
    return _guarded(workspace.import_zip, await request.body(), name, _actor(x_studio_actor))


@router.put("/strategies/{sid}/draft")
def save_draft(sid: str, request: SpecRequest) -> dict[str, Any]:
    _known(store.get, sid)
    store.save_draft(sid, request.spec or None)
    if request.spec and request.spec.get("code"):
        with contextlib.suppress(ValidationError):  # an invalid draft is still saved above; it just has no snapshot
            workspace.snapshot(sid, request.spec)
    return {"saved": True}


class MetaRequest(BaseModel):
    name: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    archived: bool | None = None
    pinned: bool | None = None


@router.patch("/strategies/{sid}")
def update_strategy(sid: str, request: MetaRequest) -> dict[str, Any]:
    _known(store.get, sid)
    if request.pinned is not None:
        home_rules.pin(sid, request.pinned)
    out = store.update_meta(sid, **request.model_dump(exclude={"pinned"}))
    return {**out, "pinned": sid in home_rules.prefs_get()["pinned"]}


@router.post("/strategies/{sid}/duplicate")
def duplicate_strategy(sid: str, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    return _known(store.duplicate, sid, _actor(x_studio_actor))


@router.get("/strategies/{sid}/ledger")
def get_ledger(sid: str) -> dict[str, Any]:
    _known(store.get, sid)
    return store.ledger(sid)


@router.get("/runs")
def runs(limit: int = 20) -> dict[str, Any]:
    return {"runs": store.recent_runs(limit)}


@router.get("/actor-log")
def actor_log(strategy_id: str | None = None) -> dict[str, Any]:
    return {"log": store.actor_log(strategy_id)}


def _failed_runs() -> dict[str, float]:
    """Strategy id to the time of its latest failed Studio job."""
    out: dict[str, float] = {}
    for j in list(JOBS._jobs.values()):  # JobStore has no listing; shortcut: reads its in-memory map
        sid = ((j.get("params") or {}).get("payload") or {}).get("strategy_id")
        if sid and j.get("status") == "failed" and str(j.get("type", "")).startswith("studio_v3_"):
            out[sid] = max(out.get(sid, 0), dt.datetime.fromisoformat(j["created_at"]).timestamp())
    return out


@router.get("/home")
def home() -> dict[str, Any]:
    prefs = home_rules.prefs_get()
    cards, fresh = home_rules.pinned_first(store.list_strategies(), prefs["pinned"]), limits.freshness()
    return {"strategies": cards, "prefs": prefs, "attention": home_rules.attention(cards, _failed_runs(), fresh), "recent_runs": store.recent_runs(8), "freshness": fresh, "live": home_rules.live_block(cards)}


def _refuse(fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    except ValueError as exc:
        raise HTTPException(422, {"refused": True, "reason": str(exc)}) from exc


class FiltersRequest(BaseModel):
    filters: list[dict[str, Any]]


@router.get("/home/filters")
def get_filters() -> dict[str, Any]:
    return {"filters": home_rules.filters_get()}


@router.put("/home/filters")
def put_filters(request: FiltersRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    _human_only(x_studio_actor, "Saving filters")
    return {"filters": _refuse(home_rules.filters_put, request.filters)}


@router.get("/home/prefs")
def get_prefs() -> dict[str, Any]:
    return home_rules.prefs_get()


@router.put("/home/prefs")
def put_prefs(request: dict[str, Any], x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    _human_only(x_studio_actor, "Saving Home preferences")
    return _refuse(home_rules.prefs_put, request)


class CompareRequest(BaseModel):
    ids: list[str]


@router.post("/compare")
def compare(request: CompareRequest) -> dict[str, Any]:
    return _refuse(home_rules.compare, request.ids, RESULTS_DIR)


class SignalsRequest(BaseModel):
    csv: str
    name: str = "Imported signals"


def _save_import(spec: dict, found: dict, save: bool, folder: str, actor: str | None, ok: bool) -> dict[str, Any]:
    found = {**found, "compile": compiler.compile_spec(_spec(spec)) if spec else None}
    found["saved"] = store.create(_spec(spec), _actor(actor), folder) if save and ok and found["compile"]["ok"] else None
    return found


@router.post("/strategies/import/signals")
def import_signals(request: SignalsRequest, save: bool = False, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Validate the CSV against the panel and show findings first; save=true saves a strategy that trades the signals (H-20)."""
    out = imports.signals(request.csv, request.name)
    return _save_import(out["spec"], out, save, "", x_studio_actor, out["ok"])


class BulkRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/strategies/rerun")
def bulk_rerun(request: BulkRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Queue one backtest per strategy over the same range (H-25). A strategy that cannot start is listed with its reason."""
    jobs, refused = [], []
    for sid in dict.fromkeys(request.ids):
        try:
            jobs.append({"id": sid, **create_job("st01", FeatureRequest(payload={**request.payload, "strategy_id": sid, "spec": None}), x_studio_actor)})
        except HTTPException as exc:
            refused.append({"id": sid, "reason": exc.detail})
    return {"jobs": jobs, "refused": refused}


@router.post("/strategies/export")
def bulk_export(request: BulkRequest) -> Response:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for sid in dict.fromkeys(request.ids):
            s = _known(store.get, sid)
            z.writestr(f"{re.sub(r'[^A-Za-z0-9._-]+', '_', s['name']) or 'strategy'}-{sid}.json", json.dumps({"name": s["name"], "version": s["version"], "spec": s["spec"]}, indent=2))
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="studio-strategies.zip"'})


@router.get("/search")
def search_strategies(q: str = "") -> dict[str, Any]:
    return {"strategies": store.search(q)}


@router.get("/trash")
def trash() -> dict[str, Any]:
    return {"strategies": store.list_trash(), "days": store.TRASH_DAYS}


def _human_only(actor: str | None, what: str) -> str:
    a = _actor(actor)
    if a.startswith("agent"):
        raise HTTPException(403, f"{what} needs a human click")
    return a


@router.post("/strategies/{sid}/trash")
def trash_strategy(sid: str, restore: bool = False, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    _human_only(x_studio_actor, "Moving to trash")
    _known(store.get, sid)
    return store.trash(sid, restore)


@router.delete("/strategies/{sid}")
def delete_strategy(sid: str, confirm: str = "", x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Permanent delete: the typed `confirm` must equal the strategy name (H-10)."""
    actor = _human_only(x_studio_actor, "Deleting")
    _known(store.get, sid)
    try:
        store.hard_delete(sid, confirm, actor)
    except ValueError as exc:
        raise HTTPException(422, {"refused": True, "reason": str(exc)}) from exc
    return {"deleted": sid}


# --- jobs ------------------------------------------------------------------------


def _finish(job_id: str | None, feature_id: str, payload: dict[str, Any], result: dict[str, Any], actor: str) -> dict[str, Any]:
    """Count the trial, log the actor, attach the ledger: the same for UI jobs and agent calls."""
    trial = result.pop("_trial", None)
    many = result.pop("_trials", None)
    meta = result["meta"]
    sid = (meta.get("strategy") or {}).get("id")
    if sid and many:
        for t in many:  # every sweep cell is a try (O-3)
            store.record_trial(sid, t["hash"], actor, "optimise", t["sharpe"], t["returns"])
        meta["ledger"] = store.ledger(sid, detail=False)
    elif sid and trial is not None:
        store.record_trial(sid, meta["run_hash"], actor, payload.get("trial_kind") or "backtest", trial["sharpe"], trial["returns"])
        meta["ledger"] = store.ledger(sid, detail=False)
    elif sid:  # a run that is not a new try (Validate) still shows the strategy's ledger
        meta["ledger"] = store.ledger(sid, detail=False)
    else:
        meta["ledger"] = {"raw": 1, "effective": 1.0, "by_actor": {}, "unsaved": True}
    meta["actor"] = actor
    if job_id:
        eq = result["charts"].get("equity_curve", [])
        step = max(1, len(eq) // 60)
        fwd = result["charts"].get("forward") or []
        paper_day = fwd[-1]["paper"] / fwd[-2]["paper"] - 1 if len(fwd) > 1 else None
        store.record_run(job_id, sid, (meta.get("strategy") or {}).get("version"), feature_id, meta["run_hash"], meta["result_hash"],
                         {"headline": meta["headline"], "total_return": meta["total_return"], "sharpe": meta["metrics"].get("sharpe"), "trades": meta["metrics"].get("trades"),
                          "spark": [round(r["strategy"], 2) for r in eq[::step]],
                          **({"drift": bool((meta.get("forward") or {}).get("drift")), "paper_day": paper_day} if feature_id == "st05" else {})})
    store.log(actor, feature_id, sid, {"run_hash": meta["run_hash"], "job_id": job_id})
    return result


def _execute(job_id: str, feature_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
    last: dict[str, Any] = {}

    def progress(name: str, pct: float, partial: Any = None) -> None:
        if partial is not None:
            last["partial"] = partial  # kept across the updates in between
        JOBS.update(job_id, progress={"percent": pct, "message": name, **last})

    progress.cancelled = lambda: (JOBS.get(job_id) or {}).get("status") == "cancelled"  # type: ignore[attr-defined]
    result = run_feature(feature_id, payload, progress)
    result = _finish(job_id, feature_id, payload, result, actor)
    result["meta"]["run"] = {"id": job_id, "feature_id": feature_id, "payload": payload}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, allow_nan=False))
    tmp.replace(path)
    return {"result_file": path.name}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: FeatureRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    try:
        feature = get_feature(feature_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        parse_payload(request.payload)  # a run that cannot start is refused here, not as a failed job
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    job = JOBS.create(job_type=f"studio_v3_{feature.FEATURE_ID}", params={"feature_id": feature.FEATURE_ID, "payload": request.payload, "data_version": data.data_version()})
    if job["status"] == "queued":
        JOBS.submit(job["job_id"], _execute, job["job_id"], feature.FEATURE_ID, {**request.payload, "_actor": _actor(x_studio_actor)}, _actor(x_studio_actor))
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": feature.FEATURE_ID}


class BuildRunRequest(BaseModel):
    level: Literal["quick", "full"] = "quick"
    spec: dict[str, Any] | None = None
    strategy_id: str | None = None
    version: int | None = Field(default=None, ge=1)
    settings: dict[str, Any] = Field(default_factory=dict)  # the same flat keys as /feature/st01/jobs: symbols, fill, cost_profile, start, end ...


@router.post("/build/run")
def build_run(request: BuildRunRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Quick run: the top 50 names by liquidity over the last 5 years, never entered in the trial ledger.
    Full run: a saved version over the whole period, recorded in the ledger. Poll GET /build/run/{job_id}; cancel with DELETE /jobs/{job_id}."""
    payload = dict(request.settings)
    if request.level == "full":
        if not request.strategy_id:
            raise HTTPException(422, "A full run needs a saved strategy. Save a version, then pass strategy_id.")
        payload.update(strategy_id=request.strategy_id, **({"version": request.version} if request.version else {}))
        label = request.strategy_id
    else:
        spec = request.spec
        if spec is None and request.strategy_id:
            spec = _known(store.get, request.strategy_id, request.version)["spec"]
        if spec is None:
            raise HTTPException(422, "A quick run needs a spec or a strategy_id.")
        label = request.strategy_id or f"draft:{spec.get('name', '')}"
        if not payload.get("symbols"):
            payload.setdefault("top_n", 50)
        if not payload.get("start"):
            panel = data.panel(["SPY"], None, None)
            if len(panel.dates):
                payload["start"] = str((panel.dates[-1] - pd.DateOffset(years=5)).date())
        payload["spec"] = spec
    job = create_job("st01", FeatureRequest(payload=payload), x_studio_actor)
    key = f"lastrun:{request.level}:{label}"
    previous = store.kv_get(key)
    store.kv_set(key, job["job_id"])
    store.kv_set(f"previous:{job['job_id']}", previous)
    return {**job, "level": request.level, "previous_job_id": previous, "budget_seconds": pycode.TIMEOUT_S}


def _run_summary(job_id: str | None) -> dict[str, Any] | None:
    path = RESULTS_DIR / f"{job_id}.json" if job_id else None
    if path is None or not path.is_file():
        return None
    meta = json.loads(path.read_text())["meta"]
    return {"total_return": meta.get("total_return"), "sharpe": (meta.get("metrics") or {}).get("sharpe"), "trades": (meta.get("metrics") or {}).get("trades")}


@router.get("/build/run/{job_id}")
def build_run_status(job_id: str) -> dict[str, Any]:
    """Job status with progress ({percent, message, partial: {symbols, bars, elapsed_seconds, budget_seconds}}) and, when done, the change since the previous run of the same level."""
    out = job_status(job_id)
    if out["status"] == "completed":
        current, previous = _run_summary(job_id), _run_summary(store.kv_get(f"previous:{job_id}"))
        out["delta"] = None if previous is None or current is None else {
            "previous_job_id": store.kv_get(f"previous:{job_id}"),
            **{k: (None if current[k] is None or previous[k] is None else current[k] - previous[k]) for k in ("total_return", "sharpe", "trades")}}
    return out


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    out = {k: job[k] for k in ("job_id", "status", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        path = RESULTS_DIR / job["result"]["result_file"]
        if not path.is_file():
            raise HTTPException(503, "Completed job result is missing from storage")
        out["result"] = json.loads(path.read_text())
    return out


@router.post("/jobs/{job_id}/reproduce")
def reproduce(job_id: str) -> dict[str, Any]:
    """Certificate: re-run a stored job from its own payload on the server and compare hashes (V-3, X-4). Nothing from the browser is trusted."""
    path = RESULTS_DIR / f"{job_id}.json"
    if not path.is_file():
        raise HTTPException(404, "Unknown run")
    stored = json.loads(path.read_text())
    run = stored["meta"].get("run") or {}
    payload = {k: v for k, v in (run.get("payload") or {}).items() if k not in ("show_holdout", "_actor")}
    fresh = run_feature(run["feature_id"], payload)
    fresh.pop("_trial", None)
    fresh.pop("_trials", None)
    a, b = stored["meta"], fresh["meta"]
    return {"job_id": job_id, "feature_id": run["feature_id"], "run_hash": a["run_hash"], "result_hash": a["result_hash"], "reproduced_hash": b["result_hash"],
            "match": a["result_hash"] == b["result_hash"], "data_version": data.data_version(), "at": time.time(),
            "grade": (b.get("grade") or {}).get("grade"), "headline": b.get("headline")}


@router.post("/jobs/{job_id}/cancel")
@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return {"job_id": job_id, "status": job["status"]}


# --- agent API: REST and MCP over the same functions (PAGES §10.5) --------------


def _agent_backtest(payload: dict[str, Any], actor: str) -> dict[str, Any]:
    """Synchronous backtest: typed spec, plain-text verdict, limits and trial ledger in the response."""
    result = _finish(None, "st01", payload, run_feature("st01", payload), actor)
    m = result["meta"]
    return {"headline": m["headline"], "verdict": "not validated", "metrics": m["metrics"], "my_limits": result["tables"]["my_limits"], "cost_ladder": result["charts"]["cost_ladder"],
            "limits": result["tables"]["limits"], "ledger": m["ledger"], "run_hash": m["run_hash"], "result_hash": m["result_hash"], "few_trades": m["few_trades"], "costs_off": m["costs_off"],
            "holdout_from": m["holdout_from"], "spec": m["spec"], "settings": m["settings"], "trades": len(result["tables"]["trades"])}


def _refusal(exc: Exception) -> HTTPException:
    if isinstance(exc, backtest.Refusal):
        return HTTPException(422, {"refused": True, "reason": exc.reason, "causes": exc.causes})
    return HTTPException(404 if isinstance(exc, KeyError) else 422, str(exc))


@router.post("/backtest")
async def agent_backtest(request: FeatureRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(_agent_backtest, request.payload, _actor(x_studio_actor or "agent"))
    except (backtest.Refusal, KeyError, ValueError, TypeError) as exc:
        raise _refusal(exc) from exc


def _tool_compile(args: dict, actor: str) -> dict:
    return compiler.compile_spec(Strategy(**args["spec"]))


def _tool_ledger(args: dict, actor: str) -> dict:
    return store.ledger(args["strategy_id"])


def _tool_optimise(args: dict, actor: str) -> dict:
    payload = args.get("payload", args)
    result = _finish(None, "st02", payload, run_feature("st02", payload), actor)
    m = result["meta"]
    return {"headline": m["headline"], "plateau": m["plateau"], "top_sets": result["tables"]["top_sets"], "importance": result["tables"]["importance"], "ledger": m["ledger"],
            "note": "every cell was counted as a trial; pick the plateau centre, not the best cell"}


def _tool_validate(args: dict, actor: str) -> dict:
    payload = {k: v for k, v in args.get("payload", args).items() if k != "show_holdout"}  # agents open the hold-out only through open_holdout
    result = _finish(None, "st03", {**payload, "_actor": actor}, run_feature("st03", {**payload, "_actor": actor}), actor)
    m = result["meta"]
    return {"grade": m["grade"], "tiles": m["tiles"], "luck": m["luck"], "next_test": m["next_test"], "what_would_change": m["what_would_change"], "ledger": m["ledger"],
            "run_hash": m["run_hash"], "result_hash": m["result_hash"]}


def _tool_open_holdout(args: dict, actor: str) -> dict:
    payload = {**args.get("payload", args), "show_holdout": True, "_actor": actor}
    m = run_feature("st03", payload)["meta"]
    return {"holdout": m["holdout"], "grade": m["grade"]["grade"], "looks_left_for_agents": validate.HOLDOUT_AGENT_BUDGET - sum(1 for x in m["holdout"]["looks"] if x["actor"].startswith("agent"))}


TOOLS: dict[str, tuple[str, dict, Any]] = {
    "list_templates": ("Twenty starter strategies as full specs.", {}, lambda a, actor: {"templates": templates.list_templates()}),
    "compile": ("Compile a strategy spec: findings with line, token and message; look-ahead is refused.", {"spec": {"type": "object"}}, _tool_compile),
    "backtest": ("Backtest a saved strategy or a spec on the development period. Returns metrics, limits and the trial ledger; every call counts as a trial.",
                 {"payload": {"type": "object", "description": "strategy_id or spec, plus run settings (symbols, top_n, start, end, costs)"}}, lambda a, actor: _agent_backtest(a.get("payload", a), actor)),
    "get_ledger": ("Raw and effective trial counts for a strategy, by actor.", {"strategy_id": {"type": "string"}}, _tool_ledger),
    "optimise": ("Sweep a saved strategy's parameter ranges (grid, random or optuna). Returns the plateau, not just the best cell; every cell counts as a trial.",
                 {"payload": {"type": "object", "description": "strategy_id, method, objective, max_cells, plus run settings"}}, _tool_optimise),
    "validate": ("Run the validation suite (walk-forward, robustness, luck, overfitting) and return the server-side grade with its reason.",
                 {"payload": {"type": "object", "description": "strategy_id, profile (quick|full), plus run settings"}}, _tool_validate),
    "get_verdict": ("Same as validate; returns only the grade, reason and what would change it.", {"payload": {"type": "object"}},
                    lambda a, actor: {k: v for k, v in _tool_validate(a, actor).items() if k in ("grade", "next_test", "what_would_change")}),
    "open_holdout": ("Open the sealed hold-out for a saved strategy. Logged; agents have 3 looks per strategy, then a human must open it.",
                     {"payload": {"type": "object", "description": "strategy_id plus run settings"}}, _tool_open_holdout),
    "get_data_audit": ("What data is held: range, tickers, adjustment, freshness.", {}, lambda a, actor: {"freshness": limits.freshness(), **limits.audit()}),
}


@router.post("/mcp")
async def mcp(request: Request, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Model Context Protocol over stateless HTTP (JSON-RPC 2.0): initialize, tools/list, tools/call."""
    body = await request.json()
    rid, method, params = body.get("id"), body.get("method"), body.get("params") or {}
    actor = _actor(x_studio_actor or "agent:mcp")
    actor = actor if actor.startswith("agent") else f"agent:{actor}"

    def ok(result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    if method == "initialize":
        return ok({"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "studio-v3", "version": "1"}})
    if method == "tools/list":
        return ok({"tools": [{"name": k, "description": d, "inputSchema": {"type": "object", "properties": schema}} for k, (d, schema, _) in TOOLS.items()]})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"Unknown tool {name}"}}
        try:
            out = await asyncio.to_thread(TOOLS[name][2], args, actor)
            if name not in ("backtest", "optimise", "validate", "get_verdict", "open_holdout"):
                store.log(actor, name, args.get("strategy_id"))
            return ok({"content": [{"type": "text", "text": json.dumps(out, default=str)}], "structuredContent": out, "isError": False})
        except backtest.Refusal as exc:
            return ok({"content": [{"type": "text", "text": str(exc)}], "structuredContent": {"refused": True, "reason": exc.reason, "causes": exc.causes}, "isError": True})
        except (KeyError, ValueError, TypeError, ValidationError) as exc:
            return ok({"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown method {method}"}}


# --- Library (page 9) ---------------------------------------------------------------


class LibraryItem(BaseModel):
    type: lib.ItemType
    name: str = Field(min_length=1, max_length=120)
    body: dict[str, Any]


class LibraryVersion(BaseModel):
    body: dict[str, Any]
    name: str | None = Field(None, max_length=120)


class CostCompare(BaseModel):
    payload: dict[str, Any]  # a st01 payload: strategy_id and version (or spec), symbols, period
    a: dict[str, Any] = Field(examples=[{"item_id": "cost-us-retail", "version": 1}])
    b: dict[str, Any]


class UniversePreview(BaseModel):
    item_id: str | None = None
    version: int | None = None
    body: dict[str, Any] | None = None
    start: str | None = None
    end: str | None = None


class BenchmarkRequest(BaseModel):
    weights: dict[str, float] | None = None
    item_id: str | None = None
    start: str | None = None
    end: str | None = None


class RegimeRequest(BaseModel):
    item_id: str | None = None
    body: dict[str, Any] | None = None
    start: str | None = None
    end: str | None = None


class MetricRequest(BaseModel):
    item_id: str | None = None
    formula: str | None = None
    metrics: dict[str, Any] | None = None  # a finished run's metrics dict
    payload: dict[str, Any] | None = None  # or a st01 payload to run now


def _lib(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except KeyError as exc:
        raise HTTPException(404, str(exc.args[0])) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _lib_body(item_id: str | None, body: dict | None, kind: str, version: int | None = None) -> dict:
    if body is not None:
        return lib._validate(kind, body)
    if not item_id:
        raise ValueError("Give item_id or body")
    it = lib.get(item_id, version)
    if it["type"] != kind:
        raise ValueError(f"{item_id} is a {it['type']}, not a {kind}")
    return it["body"]


@router.get("/library")
def library_list(type: str | None = None, include_archived: bool = False) -> dict[str, Any]:
    return {"items": lib.list_items(type, include_archived)}


@router.post("/library")
def library_create(req: LibraryItem) -> dict[str, Any]:
    return _lib(lib.create, req.type, req.name, req.body)


@router.get("/library/data/audit")
def library_data_audit() -> dict[str, Any]:
    return {"freshness": limits.freshness(), **limits.audit()}


@router.get("/library/data/catalog")
def library_catalog(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), q: str = "") -> dict[str, Any]:
    return lib.catalog(offset, limit, q)


@router.post("/library/cost-compare")
def library_cost_compare(req: CostCompare) -> dict[str, Any]:
    def run():
        spec, settings, _, _ = parse_payload(req.payload)
        return lib.compare_costs(spec, settings, req.a, req.b)

    try:
        return _lib(run)
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/library/universe/preview")
def library_universe_preview(req: UniversePreview) -> dict[str, Any]:
    return _lib(lambda: lib.universe_preview(lib.UniverseBody(**_lib_body(req.item_id, req.body, "universe", req.version)), req.start, req.end))


@router.post("/library/benchmark/series")
def library_benchmark(req: BenchmarkRequest) -> dict[str, Any]:
    return _lib(lambda: lib.benchmark_series(req.weights or _lib_body(req.item_id, None, "benchmark")["weights"], req.start, req.end))


@router.post("/library/regime/evaluate")
def library_regime(req: RegimeRequest) -> dict[str, Any]:
    return _lib(lambda: lib.regime_spans(lib.RegimeBody(**_lib_body(req.item_id, req.body, "regime")), req.start, req.end))


@router.post("/library/metric/evaluate")
def library_metric(req: MetricRequest) -> dict[str, Any]:
    def run():
        expr = req.formula or _lib_body(req.item_id, None, "metric")["formula"]
        lib.MetricBody(formula=expr)
        metrics = req.metrics
        if metrics is None:
            if req.payload is None:
                raise ValueError("Give metrics or payload")
            spec, settings, _, _ = parse_payload(req.payload)
            metrics = backtest.run_backtest(spec, settings)["meta"]["metrics"]
        return {"formula": expr, "value": lib.eval_metric(expr, metrics)}

    try:
        return _lib(run)
    except backtest.Refusal as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/library/profile/import")
def library_profile_import(doc: dict[str, Any]) -> dict[str, Any]:
    return _lib(lib.import_profile, doc)


@router.get("/library/{item_id}/export")
def library_profile_export(item_id: str, version: int | None = None) -> dict[str, Any]:
    return _lib(lib.export_profile, item_id, version)


@router.get("/library/{item_id}")
def library_get(item_id: str, version: int | None = None) -> dict[str, Any]:
    return _lib(lib.get, item_id, version)


@router.post("/library/{item_id}/versions")
def library_version(item_id: str, req: LibraryVersion) -> dict[str, Any]:
    return _lib(lib.add_version, item_id, req.body, req.name)


@router.delete("/library/{item_id}")
def library_archive(item_id: str) -> dict[str, Any]:
    return _lib(lib.archive, item_id)


# ── Paper book: a Portfolio deployed as one book (P-20) ──────────────────────
class BookMember(BaseModel):
    strategy_id: str
    version: int
    weight: float = Field(ge=0)


class BookRequest(BaseModel):
    name: str = ""
    members: list[BookMember] = Field(min_length=2, max_length=12)
    as_of: str | None = None


@router.post("/books")
def freeze_book(request: BookRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    """Deploy a Portfolio to paper as one book. Needs a human click, like freezing a strategy."""
    actor = _actor(x_studio_actor)
    if actor.startswith("agent"):
        raise HTTPException(403, "Deploying to paper needs a human click")
    for m in request.members:
        _known(store.get, m.strategy_id, m.version)
    try:
        return book.freeze([m.model_dump() for m in request.members], request.name, request.as_of, actor)
    except backtest.Refusal as exc:
        raise HTTPException(422, exc.reason) from exc


@router.get("/books")
def list_books() -> dict[str, Any]:
    return {"books": book.books()}


@router.post("/books/{bid}/today")
def book_today(bid: str, req: FeatureRequest) -> dict[str, Any]:
    _, settings, _, _ = parse_payload({**req.payload, "spec": {"entry_long": "close > 0"}})
    try:
        return backtest._clean(book.run(bid, settings))
    except backtest.Refusal as exc:
        raise HTTPException(404 if "No such" in exc.reason else 422, exc.reason) from exc

# Data browser
@router.get("/data/symbols")
def data_symbols(q: str = "", flagged: bool = False, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)) -> dict[str, Any]:
    from app.services.studio_v3.core import data_browser

    return data_browser.listing(q, flagged, offset, limit)


@router.get("/data/symbols/{symbol}")
def data_symbol(symbol: str) -> dict[str, Any]:
    from app.services.studio_v3.core import data_browser

    out = data_browser.detail(symbol)
    if out is None:
        raise HTTPException(404, f"No data for {symbol}")
    return out
