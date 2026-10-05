"""Regenerate features/output_schemas.json and docs/ML_V2_CONTRACTS.md from feature result files.

Usage: python tests/ml_v2_contract_snapshot.py DIR   (DIR holds NN.json = run_feature("NN", ...) results)
"""
import json
import sys
from pathlib import Path

from app.services.ml_v2.registry import CONTRACT_VERSION, feature_manifest

KIND = {bool: "boolean", int: "number", float: "number", str: "string"}


def column_types(rows):
    cols = {}
    for row in rows:
        for k, v in row.items():
            t = KIND.get(type(v), "object" if v is not None else None)
            if t == "string" and len(v) == 10 and v[4] == "-" and v[7] == "-":
                t = "date"
            if t and cols.get(k) in (None, t):
                cols[k] = t
            cols.setdefault(k, None)
    return cols


def main(folder):
    schemas, results = {}, {p.stem: json.loads(p.read_text()) for p in Path(folder).glob("*.json")}
    for fid, result in results.items():
        for loc in ("charts", "tables"):
            for key, value in result[loc].items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    cols = column_types(value[:200])
                    wide = len(cols) > 40
                    schemas[f"{fid}.{loc}.{key}"] = {"shape": "records", "dynamic_columns": wide,
                        "columns": [] if wide else [{"name": k, "type": t or "number", "nullable": True} for k, t in cols.items()]}
                elif isinstance(value, list):
                    schemas.setdefault(f"{fid}.{loc}.{key}", {"shape": "records", "columns": []})
    out = Path("app/services/ml_v2/features/output_schemas.json")
    out.write_text(json.dumps(dict(sorted(schemas.items())), indent=1))
    lines = [f"# ML V2 contracts\n\nContract version `{CONTRACT_VERSION}`. Generated from the backend manifest; regenerate with `tests/ml_v2_contract_snapshot.py`.\n",
"""## Endpoints (prefix `/api/ml/v2`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/features` | `{contract_version, deprecated_inputs, features:[{id,title,status,inputs,outputs,known_limitations}]}` |
| GET | `/features/{id}` | One manifest row |
| POST | `/features/{id}/validate` | `{valid:true,payload}` with defaults applied, or 422 `{detail:string}` |
| POST | `/features/{id}/jobs` | Body is the flat payload; returns `{job_id,status}`; 422 on invalid inputs or unknown tickers |
| GET | `/jobs/{job_id}?include_result=true` | `{job_id,status,progress:{percent,message},error,feature_id,created_at,updated_at,result?}`; status is queued, running, completed, failed or cancelled |
| GET | `/jobs/{job_id}/result` | Result only (409 until completed) |
| POST | `/jobs/{job_id}/cancel` | Cancels at the next stage checkpoint |
| POST | `/features/{id}/run` | Synchronous run (small universes) |
| GET | `/symbols?q=&limit=` | Ticker search |
| POST | `/uploads?kind=universe` | CSV universe, returns `{upload_id,symbols}` |

## Input row
`{key,label,type,default,required,level,group,unit,help,depends_on,options?,min?,max?,integer?}`. `type` is one of select, multiselect, number, boolean, date, ticker_list, ticker, text_list, json. `level` is quick, standard or expert. `depends_on` is `{field,values}` (show when the field holds one of the values) or `{field,present:true}`; it is a display hint, not a validation rule. Unknown keys are rejected; `compute_mode` and `research_mode` are dropped.

## Result envelope
`{feature_id,status,summary_cards:[{label,value,unit,detail?}],charts:{id:records},tables:{id:records},alerts:[{level,message}],meta}`. Every list holds flat records; no NaN or inf (null instead); dates are `YYYY-MM-DD` strings. An output row's `path` (`charts.x` or `tables.x`) locates it; `type` is timeseries, bar, scatter, heatmap, kpi, table, network or dendrogram; `encoding` names the columns for x, y, series, value; `bin:true` means the client histograms raw values; `schema.columns` lists columns with type number, string, date or boolean. Heatmaps are long (`row,col,value`) except the wide `amihud_time_surface` (`dynamic_columns`: one numeric column per ticker). Outputs with `depends_on` are empty lists unless that input is set.
"""]
    for f in feature_manifest():
        lines.append(f"\n## Feature {f['id']}: {f['title']}\n\n### Inputs\n\n| key | type | default | level | unit | range/options | depends_on |\n|---|---|---|---|---|---|---|")
        for i in f["inputs"]:
            rng = i.get("options") if "options" in i else (f"{i.get('min','')}..{i.get('max','')}" if i["type"] == "number" else "")
            lines.append(f"| `{i['key']}` | {i['type']} | `{json.dumps(i['default'])}` | {i['level']} | {i['unit']} | {rng} | {json.dumps(i['depends_on']) if i['depends_on'] else ''} |")
        lines.append("\n### Outputs\n\n| id | type | path | encoding | columns |\n|---|---|---|---|---|")
        for o in f["outputs"]:
            sch = o["schema"] or {}
            cols = "dynamic" if sch.get("dynamic_columns") else ", ".join(f"{c['name']}:{c['type']}" for c in sch.get("columns", []))
            lines.append(f"| `{o['id']}` | {o['type']} | `{o['path']}` | `{json.dumps(o['encoding'])}` | {cols} |")
        if f["known_limitations"]:
            lines.append("\nNot supported: " + "; ".join(f["known_limitations"]) + ".")
    Path("../docs/ML_V2_CONTRACTS.md").write_text("\n".join(lines) + "\n")


main(sys.argv[1])
