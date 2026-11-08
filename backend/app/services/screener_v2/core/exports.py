"""Lossless screen exports with declared formats and selected columns."""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .common import LIMITS, records


def build_export_payload(feature_id: str, payload: dict[str, Any], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = list(result_rows[0]) if result_rows else []
    chosen = payload.get('columns')
    if chosen is not None:
        if not isinstance(chosen, list) or not chosen or not all(isinstance(value, str) for value in chosen):
            raise ValueError('columns must be a nonempty JSON list of field names')
        unknown = set(chosen) - set(columns)
        if unknown and result_rows:
            raise ValueError(f'Unknown export columns: {sorted(unknown)}')
        columns = list(dict.fromkeys(chosen))
    frame = pd.DataFrame(result_rows).reindex(columns=columns)
    rows = records(frame)
    csv_text, tsv = frame.to_csv(index=False), frame.to_csv(index=False, sep='\t')
    ticker_list = '\n'.join(str(row['ticker']) for row in result_rows if row.get('ticker'))
    json_payload = {'payload': payload, 'limits': list(LIMITS), 'rows': rows}
    # Downloads carry their limits; the raw csv/tsv fields stay parser-clean.
    limit_header = ''.join(f'# {limit}\n' for limit in LIMITS)
    format = str(payload.get('export_format', 'csv')).lower()
    formats = {'csv': (limit_header + csv_text, 'text/csv', 'csv'), 'tsv': (limit_header + tsv, 'text/tab-separated-values', 'tsv'),
               'json': (json.dumps(json_payload, allow_nan=False), 'application/json', 'json'),
               'tickers': (ticker_list, 'text/plain', 'txt')}
    if format not in formats:
        raise ValueError(f'Unsupported export_format: {format}')
    content, media_type, extension = formats[format]
    return {'feature_id': feature_id, 'row_count': len(rows), 'columns': columns, 'format': format,
            'content': content, 'media_type': media_type, 'filename': f'screener-v2-{feature_id}.{extension}',
            'tsv_preview': tsv[:5000], 'tsv': tsv, 'csv': csv_text, 'ticker_list': ticker_list, 'json_payload': json_payload}
