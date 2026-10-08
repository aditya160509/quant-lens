"""Lazy backend manifest and one strict entry point for all Portfolio V2 runs."""

import importlib
from copy import deepcopy
from .core.data_loader import request_scope, cutoff

ALIASES = {
    "assets": "tickers",
    "symbols": "tickers",
    "universe": "tickers",
    "aum": "portfolio_nav",
    "regimes": "regime_count",
    "simulations": "monte_carlo_paths",
    "end_date": "as_of_date",
    "sampling_frequency": "frequency",
}


def get_portfolio_v2_feature(feature_id):
    fid = str(feature_id).replace("feature_", "").replace("feature-", "").zfill(2)
    if fid not in {f"{i:02}" for i in range(1, 14)}:
        raise KeyError("Unknown Portfolio V2 feature: " + str(feature_id))
    return fid


def module_for(fid):
    return importlib.import_module(
        f"app.services.portfolio_v2.features.feature_{get_portfolio_v2_feature(fid)}"
    )


def contract_for(fid):
    fid = get_portfolio_v2_feature(fid)
    module = module_for(fid)
    return deepcopy(
        {
            "id": fid,
            "feature_id": fid,
            "spec_id": int(fid)
            if int(fid) <= 10
            else {11: 12, 12: 13, 13: 15}[int(fid)],
            "title": module.FEATURE_NAME,
            "status": "implemented",
            "inputs": module.INPUTS,
            "outputs": module.OUTPUTS,
            "aliases": {
                a: k
                for a, k in ALIASES.items()
                if k in {d["key"] for d in module.INPUTS}
            },
        }
    )


def feature_manifest():
    return [contract_for(f"{i:02}") for i in range(1, 14)]


def prepare_payload(fid, payload=None):
    from .features.inputs import coerce

    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")
    definitions = {d["key"]: d for d in contract_for(fid)["inputs"]}
    payload = dict(payload)
    for alias, key in ALIASES.items():
        if alias in payload:
            if key in payload and payload[key] != payload[alias]:
                raise ValueError(f"Conflicting {alias} and {key}")
            payload[key] = payload.pop(alias)
    if set(payload) - set(definitions):
        raise ValueError(
            "Unsupported controls: "
            + ", ".join(sorted(set(payload) - set(definitions)))
        )
    prepared = {
        key: coerce(value, definitions[key])
        for key, value in payload.items()
        if value is not None
    }
    if prepared.get("upload_id"):
        from .core.uploads import load_upload

        field, value = load_upload(prepared.pop("upload_id"))
        if field not in definitions:
            raise ValueError("Upload kind is not supported by this feature")
        if field in prepared:
            raise ValueError("Upload conflicts with inline data")
        prepared[field] = value
    # Materialize the declared defaults so discovery and execution agree.
    for key, definition in definitions.items():
        if key not in prepared and definition["default"] is not None:
            prepared[key] = deepcopy(definition["default"])
    from .core.uploads import validate_records

    for field in {
        "strategy_returns",
        "factor_returns",
        "signal_scores",
        "strategy_trades",
    }:
        if field in prepared:
            prepared[field] = validate_records(prepared[field], field)
    with request_scope(prepared):
        cutoff()
        if "tickers" in prepared:
            from .core.data_loader import parse_symbols

            prepared["tickers"] = parse_symbols(prepared)
    return prepared


def run_feature(fid, payload=None):
    prepared = prepare_payload(fid, payload)
    with request_scope(prepared):
        return module_for(fid).run(prepared)
