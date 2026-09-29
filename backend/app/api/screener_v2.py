"""HTTP access to the modular Screener V2 feature registry."""

from __future__ import annotations

import asyncio
import csv
import io
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.screener_v2.registry import feature_manifest, run_feature


router = APIRouter(prefix="/screener-v2")


class FeatureRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/features")
async def list_features() -> dict[str, Any]:
    return {"features": feature_manifest()}


@router.post("/run/{feature_id}")
async def run_screener_feature(feature_id: str, request: FeatureRequest) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(run_feature, feature_id, request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/run/{feature_id}/csv")
async def run_screener_feature_csv(
    feature_id: str,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 2 MB limit")
    try:
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
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
    return await asyncio.to_thread(run_feature, feature_id, {"tickers": tickers, "max_symbols": min(len(tickers), 5000)})


@router.post("/export/{feature_id}.csv")
async def export_screener_feature_csv(feature_id: str, request: FeatureRequest) -> Response:
    try:
        result = await asyncio.to_thread(run_feature, feature_id, {**request.payload, "export_format": "csv"})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    downloads = result.get("tables", {}).get("instant_download", [])
    csv_text = downloads[0].get("csv", "") if downloads else ""
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="screener-v2-{feature_id}.csv"'},
    )
