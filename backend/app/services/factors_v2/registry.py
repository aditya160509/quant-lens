"""Lazy Factors V2 discovery and validated request-scoped execution."""

from __future__ import annotations
import importlib
from .core.contracts import FEATURE_CONTRACTS
from .features.inputs import inputs, outputs, validate
from .core.data_loader import (
    request_scope,
    parse_symbols,
    load_market_universe,
    source_version,
)


def normalize_feature_id(value):
    raw = str(value).replace("feature_", "").replace("feature-", "").zfill(2)
    if raw not in FEATURE_CONTRACTS:
        raise KeyError(f"Unknown Factors V2 feature: {value}")
    return raw


def feature_manifest():
    return [
        {
            "feature_id": f"feature_{fid}",
            "route_id": fid,
            "title": spec["title"],
            "inputs": inputs(fid),
            "outputs": outputs(fid),
        }
        for fid, spec in FEATURE_CONTRACTS.items()
    ]


def prepare_payload(fid, payload):
    from .core.uploads import resolve_payload

    fid = normalize_feature_id(fid)
    payload = resolve_payload(validate(fid, payload))
    if not payload.get("as_of_date"):
        prices = load_market_universe()
        dates = prices.loc[prices.Ticker.eq("SPY"), "Date"]
        if dates.empty:
            raise ValueError(
                "Supply as_of_date when the observed SPY calendar is unavailable"
            )
        payload["as_of_date"] = str(dates.max().date())
    if payload.get("end_date"):
        payload["as_of_date"] = min(payload["as_of_date"], payload["end_date"])
    with request_scope(payload):
        parse_symbols(payload.get("tickers"))
        if payload.get("holdings"):
            parse_symbols([h["ticker"] for h in payload["holdings"]])
    return payload


def run_feature(fid, payload):
    fid = normalize_feature_id(fid)
    prepared = prepare_payload(fid, payload)
    with request_scope(prepared):
        module = importlib.import_module(
            f"app.services.factors_v2.features.feature_{fid}"
        )
        result = module.run(prepared)
    result.setdefault("meta", {}).update(
        payload=prepared, source_versions=source_version()
    )
    from .core.analytics import clean_json

    return clean_json(result)
