#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw'
FF_DIR = RAW_DIR / 'fama_french'
AQR_DIR = RAW_DIR / 'aqr'
REPORT = ROOT / 'docs' / 'download_report.json'


@dataclass
class FileSpec:
    name: str
    url: str
    expected_hint: str = ''


FF_FILES: List[FileSpec] = [
    FileSpec('F-F_Research_Data_Factors_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip'),
    FileSpec('F-F_Research_Data_5_Factors_2x3_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip'),
    FileSpec('F-F_Momentum_Factor_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip'),
    FileSpec('F-F_ST_Reversal_Factor_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_ST_Reversal_Factor_daily_CSV.zip'),
    FileSpec('F-F_LT_Reversal_Factor_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_LT_Reversal_Factor_daily_CSV.zip'),
    FileSpec('48_Industry_Portfolios_daily_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/48_Industry_Portfolios_daily_CSV.zip'),
    FileSpec('F-F_Research_Data_Factors_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip'),
    FileSpec('F-F_Research_Data_5_Factors_2x3_CSV.zip', 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip'),
]

# AQR keeps stable landing links; we download available public datasets directly.
AQR_FILES: List[FileSpec] = [
    FileSpec('aqr_data_library_global_style_premia.xlsx', 'https://www.aqr.com/Insights/Datasets/Style-Premia-Data-Library'),
    FileSpec('aqr_betting_against_beta.xlsx', 'https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Original-Paper-Data'),
    FileSpec('aqr_quality_minus_junk.xlsx', 'https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly'),
    FileSpec('aqr_devil_in_hml_details.xlsx', 'https://www.aqr.com/Insights/Datasets/The-Devil-in-HMLs-Details-Factors-Daily'),
]


def fetch(url: str, out: Path, retries: int = 3) -> dict:
    err = ''
    for i in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                out.write_bytes(r.content)
                return {'ok': True, 'status': r.status_code, 'bytes': len(r.content)}
            err = f'HTTP {r.status_code}'
        except Exception as e:
            err = str(e)
        time.sleep(1.2 * i)
    return {'ok': False, 'error': err}


def extract_if_zip(path: Path) -> List[str]:
    names: List[str] = []
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path, 'r') as zf:
            for n in zf.namelist():
                if n.endswith('/'):
                    continue
                out = path.parent / Path(n).name
                out.write_bytes(zf.read(n))
                names.append(out.name)
    return names


def html_to_download_link(path: Path) -> str | None:
    # For AQR pages that return html, try find first downloadable xls/xlsx/csv link.
    try:
        txt = path.read_text(errors='ignore')
    except Exception:
        return None
    m = re.search(r'https?://[^"\']+\.(?:xlsx|xls|csv)', txt, flags=re.I)
    return m.group(0) if m else None


def main() -> int:
    FF_DIR.mkdir(parents=True, exist_ok=True)
    AQR_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    report = {'fama_french': [], 'aqr': []}

    for spec in FF_FILES:
        out = FF_DIR / spec.name
        meta = fetch(spec.url, out)
        item = {'name': spec.name, 'url': spec.url, **meta}
        if meta.get('ok'):
            extracted = extract_if_zip(out)
            item['extracted'] = extracted
        report['fama_french'].append(item)

    for spec in AQR_FILES:
        out = AQR_DIR / spec.name
        meta = fetch(spec.url, out)
        item = {'name': spec.name, 'url': spec.url, **meta}
        if meta.get('ok') and out.suffix.lower() in {'.xlsx', '.xls', '.csv'}:
            item['final_file'] = out.name
        elif meta.get('ok'):
            # likely html; try discover direct data link
            dl = html_to_download_link(out)
            item['discovered_download_link'] = dl
            if dl:
                ext = Path(dl).suffix or '.xlsx'
                fixed = AQR_DIR / f"{Path(spec.name).stem}{ext}"
                meta2 = fetch(dl, fixed)
                item['followup'] = meta2
                if meta2.get('ok'):
                    item['final_file'] = fixed.name
        report['aqr'].append(item)

    REPORT.write_text(json.dumps(report, indent=2))

    ff_ok = sum(1 for x in report['fama_french'] if x.get('ok'))
    aqr_ok = sum(1 for x in report['aqr'] if x.get('ok') and (x.get('final_file') or x.get('followup', {}).get('ok')))
    print(f'Fama-French downloaded: {ff_ok}/{len(report["fama_french"])}')
    print(f'AQR downloaded/resolved: {aqr_ok}/{len(report["aqr"])}')
    print(f'Report: {REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
