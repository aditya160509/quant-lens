"""HTTP access to the modular Screener V2 feature registry."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
import threading
import time
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.screener_v2.core import explain, formula, lookup
from app.services.screener_v2.core.data_loader import (
    BACKEND_DATA,
    available_symbols,
    parse_symbols,
)
from app.services.screener_v2.core.exports import build_xlsx
from app.services.screener_v2.core.lookup import EXCHANGES
from app.services.screener_v2.registry import feature_manifest, get_feature, run_feature
from app.services.studio.jobs import JobStore

RESULTS_DIR = BACKEND_DATA / "screener_v2" / "results"
JOBS = JobStore(path=BACKEND_DATA / "screener_v2" / "jobs.json")

router = APIRouter(prefix="/screener-v2")


class FeatureRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class RowsRequest(BaseModel):
    rows: list[dict[str, Any]]


@router.get("/features")
async def list_features() -> dict[str, Any]:
    return {"features": feature_manifest(), "capabilities": {"saved_screens": True, "reusable_universes": True, "uploads": ["universe"], "recurring_schedules": {"interval_seconds_min": 60, "interval_seconds_max": 604800}, "email_delivery": False}}


@router.post("/run/{feature_id}")
async def run_screener_feature(feature_id: str, request: FeatureRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(run_feature, feature_id, request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/run/{feature_id}/csv")
async def run_screener_feature_csv(
    feature_id: str,
    file: Annotated[UploadFile, File()],
    payload: Annotated[str, Form()] = "{}",
) -> dict[str, Any]:
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 2 MB limit")
    try:
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail="Invalid UTF-8 CSV") from exc
    tickers = []
    for row in rows:
        if not row:
            continue
        candidate = row[0].strip()
        if candidate and candidate.lower() not in {"ticker", "tickers", "symbol", "symbols"}:
            tickers.append(candidate)
    if not tickers:
        raise HTTPException(status_code=422, detail="CSV contains no ticker symbols in its first column")
    try:
        fields = json.loads(payload)
        if not isinstance(fields, dict):
            raise TypeError("payload must be a JSON object")
        return await asyncio.to_thread(run_feature, feature_id, {**fields, "tickers": tickers, "max_symbols": min(len(tickers), 5000)})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/export/{feature_id}.csv")
async def export_screener_feature_csv(feature_id: str, request: FeatureRequest) -> Response:
    try:
        feature = get_feature(feature_id)
        if feature.id != "08":
            raise ValueError("CSV export requires feature 08")
        result = await asyncio.to_thread(run_feature, feature_id, {**request.payload, "export_format": "csv"})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    downloads = result.get("tables", {}).get("instant_download", [])
    if not downloads or "csv" not in downloads[0]:
        raise HTTPException(500, "Export result is missing its declared download")
    csv_text = downloads[0]["csv"]
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="screener-v2-{feature_id}.csv"'},
    )


@router.post("/export/xlsx")
async def export_rows_xlsx(request: RowsRequest) -> Response:
    return Response(
        content=build_xlsx(request.rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="screener-v2.xlsx"'},
    )


@router.get("/facets")
async def facets() -> dict[str, Any]:
    """Every value a filter can take, with how many names hold it."""
    from app.services.screener_v2.core.screener import RANGE_FILTERS, country_of

    def build():
        p = lookup.panel()
        columns = {"sector": p.sector, "industry": p.industry, "exchange": p.exchange, "country": p.ticker.map(country_of), "currency": p.quote_currency.fillna("Unknown")}
        out = {k: [{"name": str(n), "count": int(c)} for n, c in col.value_counts().items()] for k, col in columns.items()}
        # Numeric metrics a rule can test, with how many names have a value.
        out["metric"] = [{"name": lo[:-4], "label": label, "count": int(p[col].notna().sum())} for col, lo, _, label in RANGE_FILTERS if col in p]
        return out
    return await asyncio.to_thread(_lookup_call, build)


@router.get("/templates")
async def templates() -> dict[str, Any]:
    from app.services.screener_v2.core.screener import (
        SCREEN_TEMPLATES,
        WEAK_EVIDENCE,
        template_formula,
    )
    return {"templates": [{"key": k, "formula": template_formula(v), "weak_evidence": k in WEAK_EVIDENCE} for k, v in SCREEN_TEMPLATES.items()]}


@router.get("/symbols")
def search_symbols(q: str = Query("", max_length=40), limit: int = Query(25, ge=1, le=100), exchange: str | None = Query(None, max_length=40)) -> dict[str, Any]:
    from app.services.screener_v2.core.fundamentals import _company_names

    text = q.strip().upper()
    ticker_q = text.replace(".", "_").replace("-", "_")
    names = _company_names()
    try:
        symbols = available_symbols()
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    hits = []
    for s in symbols:
        if exchange and EXCHANGES.get(s.rsplit("_", 1)[1] if "_" in s else "", "Unknown") != exchange:
            continue
        name = names.get(s) or names.get(s.replace("_", "-")) or names.get(s.replace("_", "."))
        in_name = bool(text) and name is not None and text in name.upper()
        if ticker_q in s or in_name:
            hits.append((not s.startswith(ticker_q), not (name or "").upper().startswith(text), s, name))
    hits.sort()
    return {"total": len(hits), "results": [{"ticker": s, "company_name": name, "type": "Stock", "exchange": EXCHANGES.get(s.rsplit("_", 1)[1] if "_" in s else "", "Unknown")} for _, _, s, name in hits[:limit]]}


def _lookup_call(fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, exc.args[0]) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/lookup/popular")
async def lookup_popular() -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.popular)


@router.get("/lookup/compare")
async def lookup_compare(tickers: str = Query(..., max_length=400)) -> dict[str, Any]:
    names = [t for t in tickers.replace(",", " ").split() if t]
    if not 2 <= len(names) <= 25:
        raise HTTPException(422, "Compare 2 to 25 names")
    return await asyncio.to_thread(_lookup_call, lookup.compare, names)


@router.post("/lookup/lenses")
async def lookup_lenses(body: dict[str, Any]) -> dict[str, Any]:
    names = [str(t) for t in body.get("tickers", []) if str(t).strip()][:5000]
    if not names:
        raise HTTPException(422, "Send at least one ticker")
    return await asyncio.to_thread(_lookup_call, lookup.lenses, names)


@router.post("/lookup/red-flags")
async def lookup_red_flags(body: dict[str, Any]) -> dict[str, Any]:
    names = [str(t) for t in body.get("tickers", []) if str(t).strip()][:5000]
    if not names:
        raise HTTPException(422, "Send at least one ticker")
    return await asyncio.to_thread(_lookup_call, lookup.red_flags, names)


@router.get("/lookup/{ticker}")
async def lookup_ticker(ticker: str) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.lookup, ticker)


@router.get("/lookup/{ticker}/then")
async def lookup_then(ticker: str, days: int = Query(365, ge=30, le=1825)) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.then_and_now, ticker, days)


@router.get("/lookup/{ticker}/statements")
async def lookup_statements(ticker: str, period: str = Query("annual", pattern="^(annual|quarterly)$"), all_lines: bool = False) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.statements, ticker, period, all_lines)


@router.get("/lookup/{ticker}/ohlcv")
async def lookup_ohlcv(ticker: str, days: int = Query(400, ge=20, le=4000)) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, explain.ohlcv, ticker, days)


@router.get("/lookup/{ticker}/pe-history")
async def lookup_pe_history(ticker: str, days: int = Query(756, ge=20, le=2520)) -> dict[str, Any]:
    from app.services.screener_v2.core.valuation import historical_valuation_series
    symbol = lookup.normalize_symbol(ticker)
    series = await asyncio.to_thread(_lookup_call, historical_valuation_series, symbol, "trailing_pe", days)
    return {"ticker": symbol, "metric": "trailing_pe", "series": series, "note": None if series else "No statements or prices to reprice trailing P/E for this name"}


@router.get("/lookup/{ticker}/pdf")
async def lookup_pdf(ticker: str) -> Response:
    body = await asyncio.to_thread(_lookup_call, lookup.pdf, ticker)
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{ticker}-one-page.pdf"'})


STAGE_PERCENT = {"load": 10, "compute": 40, "filter": 70, "rank": 90}


def _execute(job_id: str, feature_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = explain.RUN_ID.set(job_id)
    stage_token = explain.STAGE.set(lambda name: JOBS.update(job_id, progress={"percent": STAGE_PERCENT.get(name, 0), "message": name}))
    try:
        result = run_feature(feature_id, payload)
    finally:
        explain.STAGE.reset(stage_token)
        explain.RUN_ID.reset(token)
    from app.services.screener_v2.core.state import list_metrics
    # Everything needed to rerun this result exactly.
    result.setdefault("meta", {})["run"] = {"id": job_id, "feature_id": feature_id, "payload": payload, "metrics": list_metrics()}
    from app.services.screener_v2.core.ledger_bridge import record_trial
    record_trial(feature_id, payload, result)
    if payload.get("screen_id"):
        from app.services.screener_v2.core.notify import deliver
        deliver(str(payload["screen_id"]), result)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, allow_nan=False))
    tmp.replace(path)
    return {"result_file": path.name}


def _submit_feature(feature_id, payload, idempotency_key=None):
    from app.services.screener_v2.core.currency import instrument_context
    from app.services.screener_v2.core.data_loader import (
        CATEGORY7_MACRO,
        FF5_DAILY,
        FX_DAILY,
        MARKET_UNIVERSE,
        MASTER_FUNDAMENTALS,
        MOM_DAILY,
        default_as_of,
    )
    from app.services.screener_v2.features.inputs import normalize_payload
    feature = get_feature(feature_id)
    payload = normalize_payload(feature.inputs, payload)
    parse_symbols(payload)
    with instrument_context(payload):
        pass
    payload = {**payload, "as_of_date": payload.get("as_of_date") or default_as_of(payload)}
    versions = {path.name: path.stat().st_mtime_ns if path.exists() else None for path in [MARKET_UNIVERSE, MASTER_FUNDAMENTALS, FF5_DAILY, MOM_DAILY, CATEGORY7_MACRO, FX_DAILY]}
    job = JOBS.create(job_type=f"screener_v2_{feature.id}", params={"feature_id": feature.id, "payload": payload, "data_versions": versions}, idempotency_key=idempotency_key)
    if job["status"] == "queued":
        JOBS.submit(job["job_id"], _execute, job["job_id"], feature.id, payload)
    return {"job_id": job["job_id"], "status": job["status"], "feature_id": feature.id}


@router.post("/feature/{feature_id}/jobs")
def create_job(feature_id: str, request: FeatureRequest) -> dict[str, Any]:
    try:
        return _submit_feature(feature_id, request.payload)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


def _job_result(job: dict[str, Any]) -> dict[str, Any]:
    path = RESULTS_DIR / job["result"]["result_file"]
    if not path.is_file():
        raise HTTPException(503, "Completed job result is missing from storage")
    return json.loads(path.read_text())


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    out = {k: job[k] for k in ("job_id", "status", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        out["result"] = _job_result(job)
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"job_id": job_id, "status": job["status"], "note": "Running computation finishes; cancellation suppresses publication."}


class ExplainRequest(BaseModel):
    run_id: str
    symbol: str | None = None
    other: str | None = None


def _explained(request: ExplainRequest, fn):
    job = JOBS.get(request.run_id)
    if not job or job["status"] != "completed":
        raise HTTPException(404, "Unknown or unfinished run")
    payload = job["params"]["payload"]
    try:
        panel = explain.panel_for(request.run_id, payload)
        return fn(panel, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/explain/why")
async def explain_why(request: ExplainRequest) -> dict[str, Any]:
    return {"checks": await asyncio.to_thread(_explained, request, lambda p, f: explain.why_here(p, f, request.symbol or ""))}


@router.post("/explain/near-miss")
async def explain_near_miss(request: ExplainRequest) -> dict[str, Any]:
    return {"near_misses": await asyncio.to_thread(_explained, request, lambda p, f: explain.near_misses(explain.eligible(p, f), f))}


@router.post("/explain/difference")
async def explain_difference(request: ExplainRequest) -> dict[str, Any]:
    return {"filters": await asyncio.to_thread(_explained, request, lambda p, f: explain.explain_difference(p, f, request.symbol or "", request.other or ""))}


@router.post("/explain/sensitivity")
async def explain_sensitivity(request: ExplainRequest) -> dict[str, Any]:
    return await asyncio.to_thread(_explained, request, explain.sensitivity)


class PreviewRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list, max_length=40)


@router.post("/filters/preview")
async def filters_preview(request: PreviewRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(explain.preview, request.payload, request.fields)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


class SparkRequest(BaseModel):
    tickers: list[str]
    days: int = 92


@router.post("/sparklines")
async def sparklines(request: SparkRequest) -> dict[str, Any]:
    if not 7 <= request.days <= 1830:
        raise HTTPException(422, "days must be between 7 and 1830")
    return await asyncio.to_thread(explain.sparklines, request.tickers, request.days)


@router.get("/data-range")
async def data_range() -> dict[str, Any]:
    return await asyncio.to_thread(explain.data_range)


@router.get("/breadth")
async def market_breadth(max_symbols: int = Query(500, ge=1, le=1000)) -> dict[str, Any]:
    return await asyncio.to_thread(explain.breadth, {"universe": "master", "max_symbols": max_symbols})


@router.get("/breadth/history")
async def market_breadth_history(max_symbols: int = Query(500, ge=1, le=1000), days: int = Query(252, ge=20, le=1260)) -> dict[str, Any]:
    return await asyncio.to_thread(explain.breadth_history, {"universe": "master", "max_symbols": max_symbols}, days)


@router.get("/rrg")
async def relative_rotation(tickers: str = Query(..., max_length=400), benchmark: str = Query("SPY", max_length=40)) -> dict[str, Any]:
    names = [t for t in tickers.replace(",", " ").split() if t]
    if not 1 <= len(names) <= 50:
        raise HTTPException(422, "Rotation graph takes 1 to 50 tickers")
    return await asyncio.to_thread(_lookup_call, explain.rrg, names, benchmark)


@router.get("/filters/keys")
def filter_keys() -> dict[str, list[str]]:
    from app.services.screener_v2.core.screener import RANGE_FILTERS
    return {column: [lo, hi] for column, lo, hi, _ in RANGE_FILTERS}


class DiffRequest(BaseModel):
    before: str
    after: str


@router.post("/explain/diff")
def explain_diff(request: DiffRequest) -> dict[str, Any]:
    runs = []
    for run_id in (request.before, request.after):
        job = JOBS.get(run_id)
        if not job or job["status"] != "completed":
            raise HTTPException(404, f"Unknown or unfinished run {run_id}")
        runs.append(_job_result(job))
    names = [[r["ticker"] for r in run["tables"].get("ranked_screener_table", [])] for run in runs]
    settings = [run["meta"].get("run", {}).get("payload", {}) for run in runs]
    changed = sorted(k for k in settings[0].keys() | settings[1].keys() if settings[0].get(k) != settings[1].get(k))
    return {**explain.screen_diff(*names), "as_of": [run["meta"].get("as_of_date") for run in runs], "changed_settings": changed, "counts": [len(n) for n in names]}


class MetricRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)
    show: bool = False


@router.get("/formula/catalogue")
async def formula_catalogue() -> dict[str, Any]:
    return await asyncio.to_thread(lambda: formula.catalogue(lookup.panel()))


@router.post("/formula/preview")
async def formula_preview(request: FeatureRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(lambda: formula.preview(lookup.panel(), str(request.payload.get("formula") or "")))
    except formula.FormulaError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/metrics/{name}")
async def put_metric(name: str, request: MetricRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.state import save_metric
    panel = await asyncio.to_thread(lookup.panel)
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}", name) or name in panel.columns or name in formula.FUNCTIONS:
        raise HTTPException(422, "A metric name is lower-case letters, digits and underscores, and not an existing field or function")
    try:
        await asyncio.to_thread(formula.preview, panel, request.expression)
    except formula.FormulaError as exc:
        raise HTTPException(422, str(exc)) from exc
    return save_metric(name, request.expression, request.show)


@router.delete("/metrics/{name}")
def remove_metric(name: str) -> dict[str, str]:
    from app.services.screener_v2.core.state import delete_metric
    delete_metric(name)
    return {"deleted": name}


class SavedScreenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    feature_id: str = '01'
    payload: dict[str, Any] = Field(default_factory=dict)


class UniverseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    symbols: list[str] = Field(min_length=1, max_length=5000)


@router.get('/ledger')
def trial_ledger() -> dict[str, Any]:
    from app.services.screener_v2.core.ledger_bridge import ledger
    return ledger()


@router.get('/markets/{asset}')
async def markets(asset: str) -> dict[str, Any]:
    from app.services.screener_v2.core import nonequity
    try:
        rows = await asyncio.to_thread(nonequity.hourly if asset == 'hourly' else nonequity.screen, *([] if asset == 'hourly' else [asset]))
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return {'rows': rows}


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post('/nl-formula')
def nl_formula(request: TextRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.nl_formula import to_formula
    try:
        return to_formula(request.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/nl-filter')
def nl_filter(request: TextRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.nl_formula import to_filters
    try:
        return to_filters(request.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/screens/{screen_id}/share')
def share_screen(screen_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import create_share
    try:
        return {'token': create_share(screen_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/shares')
def shares() -> dict[str, Any]:
    from app.services.screener_v2.core.shares import list_shares
    return {'shares': list_shares()}


@router.delete('/shares/{token}')
def unshare(token: str) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import revoke_share
    revoke_share(token)
    return {'revoked': token}


@router.get('/shared/{token}')
def shared(token: str) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import shared_screen
    try:
        return shared_screen(token)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


class KeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    daily_limit: int = Field(ge=1, le=1_000_000)


@router.post('/api-keys')
def new_api_key(request: KeyRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import create_key
    return {'key': create_key(request.name, request.daily_limit)}


@router.get('/api-keys')
def api_keys() -> dict[str, Any]:
    from app.services.screener_v2.core.shares import list_keys
    return {'keys': list_keys()}


@router.delete('/api-keys/{key_id}')
def drop_api_key(key_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import revoke_key
    revoke_key(key_id)
    return {'revoked': key_id}


@router.get('/v1/screens/{screen_id}/latest')
def keyed_latest_run(screen_id: str, x_api_key: Annotated[str, Header()]) -> dict[str, Any]:
    from app.services.screener_v2.core.shares import spend
    from app.services.screener_v2.core.state import run_history
    try:
        spend(x_api_key)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(429, str(exc)) from exc
    runs = run_history(screen_id, 1)
    if not runs:
        raise HTTPException(404, 'This screen has no stored run')
    return runs[0]


@router.get('/screens')
def saved_screens() -> dict[str, Any]:
    from app.services.screener_v2.core.state import list_screens
    return {'screens': list_screens()}


@router.put('/screens/{screen_id}')
def put_screen(screen_id: str, request: SavedScreenRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.state import save_screen
    try:
        feature = get_feature(request.feature_id)
        from app.services.screener_v2.features.inputs import normalize_payload
        payload = normalize_payload(feature.inputs, request.payload)
        parse_symbols(payload)
        return save_screen(screen_id, request.name, feature.id, payload)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post('/screens/{screen_id}/jobs')
def run_saved_screen(screen_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.state import get_screen
    try:
        screen = get_screen(screen_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return create_job(screen['feature_id'], FeatureRequest(payload={**screen['payload'], 'screen_id': screen_id}))


@router.get('/screens/{screen_id}/history')
def saved_screen_history(screen_id: str, limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    from app.services.screener_v2.core.state import get_screen, run_history
    try:
        get_screen(screen_id)
        return {'runs': run_history(screen_id, limit)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


COUNT_CACHE: dict[str, int | None] = {}


def _count_key(screen: dict[str, Any]) -> str:
    from app.services.screener_v2.registry import hash_versions
    spec = [screen["feature_id"], screen["payload"], format(hash_versions(), "x")]
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()


def _screens_counts(screens: list[dict[str, Any]], budget_seconds: float) -> dict[str, Any]:
    """Live match counts, from each screen's filter funnel; screens past the time budget are left for their own page."""
    started, counts = time.monotonic(), {}
    for screen in screens:
        key = _count_key(screen)
        if key not in COUNT_CACHE:
            if time.monotonic() - started > budget_seconds:
                counts[screen["screen_id"]] = {"count": None, "reason": "time budget reached; open the screen to count"}
                continue
            try:
                funnel = run_feature(screen["feature_id"], screen["payload"]).get("charts", {}).get("filter_funnel_waterfall") or []
            except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
                counts[screen["screen_id"]] = {"count": None, "reason": str(exc)}
                continue
            COUNT_CACHE[key] = int(funnel[-1]["remaining"]) if funnel else None
        counts[screen["screen_id"]] = {"count": COUNT_CACHE[key], "reason": None if COUNT_CACHE[key] is not None else "feature has no filter funnel"}
    return {"counts": counts}


@router.get('/screens/counts')
async def saved_screen_counts(budget_seconds: float = Query(20, ge=1, le=120)) -> dict[str, Any]:
    from app.services.screener_v2.core.state import list_screens
    return await asyncio.to_thread(_screens_counts, list_screens(), budget_seconds)


@router.get('/screens/changes')
def saved_screen_changes(ids: str = Query(..., max_length=2000)) -> dict[str, Any]:
    """Entrants and exits per saved screen, between its last two stored runs."""
    from app.services.screener_v2.core.explain import screen_diff
    from app.services.screener_v2.core.state import get_screen, run_history
    screen_ids = list(dict.fromkeys(i.strip() for i in ids.split(',') if i.strip()))
    if not 1 <= len(screen_ids) <= 50:
        raise HTTPException(422, 'Compare 1 to 50 saved screens')
    changes = {}
    for screen_id in screen_ids:
        try:
            get_screen(screen_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        runs = run_history(screen_id, 2)
        if len(runs) < 2:
            changes[screen_id] = {'entrants': None, 'exits': None, 'as_of': [r['as_of_date'] for r in runs], 'reason': 'fewer than two stored runs'}
            continue
        newest, previous = (r['result']['tables'].get('ranked_screener_table', []) for r in runs)
        diff = screen_diff([row['ticker'] for row in previous], [row['ticker'] for row in newest])
        changes[screen_id] = {'entrants': diff['entered'], 'exits': diff['left'], 'as_of': [runs[0]['as_of_date'], runs[1]['as_of_date']], 'reason': None}
    return {'changes': changes}


@router.get('/universes')
def saved_universes() -> dict[str, Any]:
    from app.services.screener_v2.core.state import list_universes
    return {'universes': list_universes()}


@router.put('/universes/{universe_id}')
def put_universe(universe_id: str, request: UniverseRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.state import save_universe
    try:
        symbols = parse_symbols({'tickers': request.symbols, 'max_symbols': 5000})
        return save_universe(universe_id, request.name, symbols)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.delete('/universes/{universe_id}')
def remove_universe(universe_id: str) -> dict[str, str]:
    from app.services.screener_v2.core.state import delete_universe
    delete_universe(universe_id)
    return {'deleted': universe_id}


@router.get('/preferences')
def get_preferences() -> dict[str, Any]:
    from app.services.screener_v2.core.state import load_preferences
    return load_preferences()


@router.put('/preferences')
def put_preferences(blob: dict[str, Any]) -> dict[str, Any]:
    from app.services.screener_v2.core.state import save_preferences
    try:
        return save_preferences(blob)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/uploads')
async def upload_universe(file: Annotated[UploadFile, File()], kind: str = Query('universe')) -> dict[str, Any]:
    from app.services.screener_v2.core.data_loader import store_universe_upload
    if kind != 'universe':
        raise HTTPException(422, 'Only universe CSV uploads are supported')
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, 'Universe CSV exceeds 2 MB')
    try:
        return await asyncio.to_thread(store_universe_upload, raw, file.filename)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post('/export/{feature_id}')
async def download_screen(feature_id: str, request: FeatureRequest) -> Response:
    try:
        feature = get_feature(feature_id)
        if feature.id != '08':
            raise ValueError('Screen export requires feature 08')
        result = await asyncio.to_thread(run_feature, feature.id, request.payload)
        download = result['tables']['instant_download'][0]
        return Response(download['content'], media_type=download['media_type'],
                        headers={'Content-Disposition': f'attachment; filename="{download["filename"]}"'})
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


class ChannelsRequest(BaseModel):
    urls: list[str] = Field(max_length=10)
    digest: bool = False


@router.put('/screens/{screen_id}/channels')
def put_channels(screen_id: str, request: ChannelsRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.state import set_channels
    try:
        set_channels(screen_id, request.urls, request.digest)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return get_channels(screen_id)


@router.get('/screens/{screen_id}/channels')
def get_channels(screen_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.state import channels
    # Only the scheme is returned: the rest of an Apprise URL is a secret.
    return {'channels': [{'service': c['url'].split('://')[0], 'digest': c['digest']} for c in channels(screen_id)]}


@router.get('/screens/{screen_id}/events')
def screen_events(screen_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.state import screen_events as events
    return {'events': events(screen_id)}


@router.get('/screens/{screen_id}/precision')
def screen_precision(screen_id: str) -> dict[str, Any]:
    from app.services.screener_v2.core.alerts import realized_alert_precision
    return {'precision': realized_alert_precision(screen_id, delivered_only=True)}


class ScheduleRequest(BaseModel):
    interval_seconds: int = Field(default=86400, ge=60, le=604800)
    enabled: bool = True


@router.put('/screens/{screen_id}/schedule')
def put_schedule(screen_id: str, request: ScheduleRequest) -> dict[str, Any]:
    from app.services.screener_v2.core.state import set_schedule
    try:
        return set_schedule(screen_id, request.interval_seconds, request.enabled)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get('/schedules')
def schedules() -> dict[str, Any]:
    from app.services.screener_v2.core.state import list_schedules
    return {'schedules': list_schedules(), 'clock': 'UTC Unix seconds', 'missed_runs': 'one catch-up dispatch; no duplicate historical runs'}


from app.services.screener_v2.core.scheduler import ScreenScheduler

SCHEDULER = ScreenScheduler(_submit_feature)


@router.on_event('startup')
def start_scheduler():
    SCHEDULER.start()
    threading.Thread(target=lookup.panel, daemon=True).start()  # first quick look would otherwise wait ~30 s


@router.on_event('shutdown')
def stop_scheduler():
    SCHEDULER.stop()
