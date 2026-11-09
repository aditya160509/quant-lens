"""HTTP access to the modular Screener V2 feature registry."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import threading
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.screener_v2.core import lookup
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


@router.get("/lookup/{ticker}")
async def lookup_ticker(ticker: str) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.lookup, ticker)


@router.get("/lookup/{ticker}/statements")
async def lookup_statements(ticker: str, period: str = Query("annual", pattern="^(annual|quarterly)$"), all_lines: bool = False) -> dict[str, Any]:
    return await asyncio.to_thread(_lookup_call, lookup.statements, ticker, period, all_lines)


@router.get("/lookup/{ticker}/pdf")
async def lookup_pdf(ticker: str) -> Response:
    body = await asyncio.to_thread(_lookup_call, lookup.pdf, ticker)
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{ticker}-one-page.pdf"'})


def _execute(job_id: str, feature_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = run_feature(feature_id, payload)
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


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    out = {k: job[k] for k in ("job_id", "status", "progress", "error")}
    if job["status"] == "completed" and job.get("result"):
        path = RESULTS_DIR / job["result"]["result_file"]
        if not path.is_file():
            raise HTTPException(503, "Completed job result is missing from storage")
        out["result"] = json.loads(path.read_text())
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"job_id": job_id, "status": job["status"], "note": "Running computation finishes; cancellation suppresses publication."}


class SavedScreenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    feature_id: str = '01'
    payload: dict[str, Any] = Field(default_factory=dict)


class UniverseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    symbols: list[str] = Field(min_length=1, max_length=5000)


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
