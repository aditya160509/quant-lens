"""Backend-owned ML V2 presentation contracts and value validation."""
from __future__ import annotations
import math

def inputs(contract, defaults):
    out = []
    declared = {item["key"]: item for item in contract}
    for key in dict.fromkeys([*declared, *defaults, "as_of_date", "embargo_period"]):
        row = dict(declared.get(key, {}))
        default = row.get("default", defaults.get(key))
        row.update(key=key, label=row.get("label", key.replace("_", " ").title()),
                   group=row.get("group", "Configuration"), default=default,
                   help=row.get("description", ""))
        row.setdefault("type", "boolean" if isinstance(default, bool) else
                       "integer" if isinstance(default, int) else "number" if isinstance(default, float)
                       else "date" if key == "as_of_date" else "text")
        if "range" in row:
            row["min"], row["max"] = row["range"]
        out.append(row)
    return out

def outputs(contract):
    return [{**row, "source": row["location"], "render_hint": row["renderer"],
             "label": row["key"].replace("_", " ").title(), "primary": i == 0}
            for i, row in enumerate(contract)]

def validate(payload, contract):
    for row in contract:
        key, value = row["key"], payload.get(row["key"])
        if value is None:
            continue
        options = row.get("options")
        values = value if row.get("type") == "multi_select" else [value]
        if options is not None:
            if not isinstance(values, list) or any(v not in options for v in values):
                raise ValueError(f"Unsupported {key}={value!r}; supported values: {options}")
        if row.get("type") in {"integer", "number", "float"}:
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                number = float(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
            if not math.isfinite(number) or (row["type"] == "integer" and number != int(number)):
                raise ValueError(f"Invalid numeric {key}")
            if "min" in row and number < row["min"] or "max" in row and number > row["max"]:
                raise ValueError(f"{key} is outside its supported range")
    return payload
