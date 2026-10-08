"""Volatility V2 discovery, strict observed-data runs and durable local jobs."""
from __future__ import annotations

import asyncio
import json
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.volatility_v2.core.contracts import all_contracts
from app.services.volatility_v2.core.data_loader import BACKEND_DATA, file_version, source_version, symbol_directory
from app.services.volatility_v2.core.uploads import MAX_BYTES, save_upload, upload_path
from app.services.volatility_v2.registry import get_volatility_v2_feature, run_feature
from app.services.studio.jobs import JobStore

router = APIRouter(prefix="/labs/volatility/v2", tags=["volatility-v2"])
JOBS = JobStore(path=BACKEND_DATA / 'volatility_v2/jobs.json')
RESULTS = BACKEND_DATA / 'volatility_v2/results'


def payload_from(request):
    # Preserve the existing flat request API, but reject ambiguous mixed envelopes.
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    if 'payload' in request:
        if set(request) != {'payload'} or not isinstance(request['payload'], dict):
            raise ValueError('Expected exactly {payload: {...}}')
        return request['payload']
    return request


def sources(payload):
    versions = list(source_version())
    identifier = payload.get('iv_upload_id')
    if identifier is not None:
        versions.append(file_version(upload_path(identifier)))
    if payload.get('include_hourly_variation'):
        versions.append(file_version(BACKEND_DATA / 'canonical/cross_asset_hourly.parquet'))
    return json.loads(json.dumps(versions))


def prepare(feature_id, request):
    fid = get_volatility_v2_feature(feature_id).id
    payload = payload_from(request)
    # Resolve explicit selections before enqueueing without running estimators.
    from app.services.volatility_v2.core.data_loader import resolve_symbols
    if 'assets' in payload:
        assets = payload['assets']
        if isinstance(assets, str):
            assets = [x.strip() for x in assets.split(',') if x.strip()]
        if not isinstance(assets, list):
            raise ValueError('assets must be a list or comma-separated symbols')
        resolve_symbols(assets)
    return fid, payload


@router.get('/features')
def list_features():
    return {'status': 'ok', 'features': all_contracts()}


@router.get('/symbols')
def symbols(q: str = Query('', max_length=80), limit: int = Query(25, ge=1, le=100)):
    matches = [symbol for symbol in symbol_directory() if q.strip().upper() in symbol.upper()]
    return {'status': 'ok', 'symbols': [{'symbol': symbol} for symbol in matches[:limit]]}


@router.post('/feature/{feature_id}/run')
async def execute_feature(feature_id: str, request: dict):
    try:
        fid = get_volatility_v2_feature(feature_id).id
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        return await asyncio.to_thread(run_feature, fid, payload_from(request))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/uploads')
async def upload(kind: str = Query(...), file: UploadFile = File(...)):
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, 'IV uploads are limited to 2 MB')
    try:
        return save_upload(raw, kind)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/export/{feature_id}')
async def export(feature_id: str, request: dict):
    result = await execute_feature(feature_id, request)
    return {'status': result['status'], 'formats': ['json', 'csv_tables'], 'json': result,
            'csv_tables': {key: pd.DataFrame(rows).to_csv(index=False)
                           for key, rows in result.get('tables', {}).items() if isinstance(rows, list)}}


def _execute(job_id, fid, payload):
    expected = JOBS.get(job_id)['params']['source_versions']
    if sources(payload) != expected:
        raise ValueError('Data changed after enqueueing; rerun against a consistent source version')
    # Publish no fabricated percentage for long, indivisible estimator fits.
    JOBS.update(job_id, progress={'percent': None, 'message': f'Estimating feature {fid}'})
    result = run_feature(fid, payload)
    if sources(payload) != expected:
        raise ValueError('Data changed during estimation; result was not published')
    if result.get('status') == 'error':
        raise ValueError(result.get('meta', {}).get('error', 'Feature failed'))
    if JOBS.get(job_id)['status'] == 'cancelled':
        return {}
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f'{job_id}.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, allow_nan=False))
    temp.replace(path)
    return {'result_file': path.name}


@router.post('/feature/{feature_id}/jobs')
def create_job(feature_id: str, request: dict):
    try:
        fid = get_volatility_v2_feature(feature_id).id
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        fid, payload = prepare(fid, request)
        versions = sources(payload)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    job = JOBS.create(job_type=f'volatility_v2_{fid}', params={
        'feature_id': fid, 'payload': payload, 'source_versions': versions,
    })
    JOBS.submit(job['job_id'], _execute, job['job_id'], fid, payload)
    return {'job_id': job['job_id'], 'status': job['status'], 'feature_id': fid}


@router.get('/jobs/{job_id}')
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, 'Unknown job')
    out = {key: job[key] for key in ['job_id', 'status', 'progress', 'error', 'created_at', 'updated_at']}
    if job['status'] == 'completed':
        out['result'] = json.loads((RESULTS / job['result']['result_file']).read_text())
    return out


@router.post('/jobs/{job_id}/cancel')
def cancel(job_id: str):
    job = JOBS.cancel(job_id)
    if not job:
        raise HTTPException(404, 'Unknown job')
    return {'job_id': job_id, 'status': job['status'],
            'note': 'Cancellation suppresses publication; an active estimator finishes in the background'}
