"""HTTP and MCP access to Studio v3. Every result is computed here; the browser never posts one back (PLAN §3.5)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError

from app.services.screener_v2.core.data_loader import BACKEND_DATA, normalize_symbol
from app.services.studio.jobs import JobStore
from app.services.studio_v3.core import (
    backtest,
    data,
    formula,
    limits,
    live,
    plain,
    pycode,
    store,
    templates,
    validate,
)
from app.services.studio_v3.core import compile as compiler
from app.services.studio_v3.core.spec import Strategy
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
    if tf not in {"1d", "1h", "1w", "1mo"} or not names:
        raise HTTPException(422, "tf must be 1d, 1h, 1w or 1mo, with at least one symbol")
    out: dict[str, Any] = {}
    if tf == "1h":
        from app.services.screener_v2.core import data_loader, performance

        h = data._hourly(performance._path_version(data_loader.MARKET_UNIVERSE_HOURLY))
        for s in names:
            rows = h.filter(h["Ticker"] == s)
            if start:
                rows = rows.filter(rows["Datetime"] >= pd.Timestamp(start))
            if end:
                rows = rows.filter(rows["Datetime"] <= pd.Timestamp(end) + pd.Timedelta(days=1))
            out[s] = [{"time": int(t.timestamp()), "open": o, "high": hi, "low": lo, "close": c, "volume": v}
                      for t, o, hi, lo, c, v in zip(rows["Datetime"].to_list(), rows["Open"].to_list(), rows["High"].to_list(), rows["Low"].to_list(), rows["Close"].to_list(), rows["Volume"].to_list(), strict=True)]
        return {"tf": tf, "bars": out, "hourly_names": list(data.hourly_symbols())}
    p = data.panel(names, start, end)
    for i, s in enumerate(p.symbols):
        df = pd.DataFrame({f: getattr(p, f)[:, i] for f in data.FIELDS}, index=p.dates).dropna(subset=["close"])
        if tf in _RULE:
            df = df.resample(_RULE[tf]).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["close"])
        out[s] = [{"time": str(d.date()), "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": 0.0 if np.isnan(r.volume) else r.volume} for d, r in zip(df.index, df.itertuples(), strict=True)]
    return {"tf": tf, "bars": out, "missing": [s for s in names if s not in out], "hourly_names": list(data.hourly_symbols())}


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


class PreviewRequest(BaseModel):
    spec: dict
    symbol: str = "SPY"


@router.post("/preview")
def preview(request: PreviewRequest) -> dict[str, Any]:
    try:
        return backtest.preview(_spec(request.spec), request.symbol)
    except backtest.Refusal as exc:
        return {"status": "skipped", "reason": exc.reason, "bars": [], "trades": []}
    except pycode.CodeError as exc:
        return {"status": "error", "reason": exc.message, "line": exc.line, "bars": [], "trades": []}


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


@router.get("/templates")
def get_templates() -> dict[str, Any]:
    return {"templates": templates.list_templates()}


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


@router.get("/strategies/{sid}")
def get_strategy(sid: str, version: int | None = None) -> dict[str, Any]:
    return _known(store.get, sid, version)


@router.put("/strategies/{sid}")
def save_version(sid: str, request: SpecRequest, x_studio_actor: str | None = Header(None)) -> dict[str, Any]:
    return _known(store.save_version, sid, _spec(request.spec), _actor(x_studio_actor))


@router.put("/strategies/{sid}/draft")
def save_draft(sid: str, request: SpecRequest) -> dict[str, Any]:
    _known(store.get, sid)
    store.save_draft(sid, request.spec or None)
    return {"saved": True}


class MetaRequest(BaseModel):
    name: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    archived: bool | None = None


@router.patch("/strategies/{sid}")
def update_strategy(sid: str, request: MetaRequest) -> dict[str, Any]:
    _known(store.get, sid)
    return store.update_meta(sid, **request.model_dump())


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


@router.get("/home")
def home() -> dict[str, Any]:
    cards, fresh = store.list_strategies(), limits.freshness()
    attention = []
    if fresh["tone"] != "ok":
        attention.append({"kind": "data", "tone": fresh["tone"], "text": fresh["label"], "action": {"label": "Open data", "href": "/studio/library/data"}})
    for c in cards:
        if c["has_draft"]:
            attention.append({"kind": "draft", "tone": "amber", "strategy_id": c["id"], "text": f"{c['name']}: unsaved draft", "action": {"label": "Open", "href": f"/studio/build/{c['id']}"}})
    return {"strategies": cards, "attention": attention, "recent_runs": store.recent_runs(8), "freshness": fresh}


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
        store.record_run(job_id, sid, (meta.get("strategy") or {}).get("version"), feature_id, meta["run_hash"], meta["result_hash"],
                         {"headline": meta["headline"], "total_return": meta["total_return"], "sharpe": meta["metrics"].get("sharpe"), "trades": meta["metrics"].get("trades"),
                          "spark": [round(r["strategy"], 2) for r in eq[::step]]})
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
    "get_data_audit": ("What data is held: range, tickers, hourly coverage, adjustment, freshness.", {}, lambda a, actor: {"freshness": limits.freshness(), **limits.audit()}),
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
