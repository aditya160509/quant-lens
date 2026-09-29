#!/usr/bin/env python3
"""Convert AQR real Excel files to CSV tabs; skip html masquerading files."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AQR_RAW = ROOT / 'factors/data/raw/aqr'
AQR_CSV = ROOT / 'factors/data/processed/aqr_csv'


def safe_name(s: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in s).strip('_')


def is_real_excel(path: Path) -> bool:
    with path.open('rb') as f:
        sig = f.read(8)
    # xlsx starts with PK\x03\x04 (zip container)
    return sig.startswith(b'PK\x03\x04')


def main() -> int:
    AQR_CSV.mkdir(parents=True, exist_ok=True)
    files = sorted(AQR_RAW.glob('*.xlsx')) + sorted(AQR_RAW.glob('*.xls'))
    if not files:
        print('No AQR Excel files found in', AQR_RAW)
        return 1

    converted = 0
    skipped = []
    for f in files:
        if not is_real_excel(f):
            skipped.append(f.name)
            continue
        xls = pd.ExcelFile(f)
        stem = safe_name(f.stem)
        for sheet in xls.sheet_names:
            df = pd.read_excel(f, sheet_name=sheet)
            out = AQR_CSV / f"{stem}__{safe_name(sheet)}.csv"
            df.to_csv(out, index=False)
            converted += 1

    print('Converted sheets:', converted)
    if skipped:
        print('Skipped non-excel files:', skipped)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
