#!/usr/bin/env python3
from __future__ import annotations

import re
import json
from pathlib import Path
from urllib.parse import urljoin
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'raw' / 'aqr'
REPORT = ROOT / 'docs' / 'aqr_real_download_report.json'

PAGES = [
    'https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Original-Paper-Data',
    'https://www.aqr.com/Insights/Datasets/The-Devil-in-HMLs-Details-Factors-Daily',
    'https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly',
]

# prefer these exact filenames if found
PREFERRED = {
    'Betting-Against-Beta-Equity-Factors-Daily.xlsx',
    'The-Devil-in-HMLs-Details-Factors-Daily.xlsx',
    'Quality-Minus-Junk-Factors-Daily.xlsx',
    'Quality-Minus-Junk-Factors-Monthly.xlsx',
}


def extract_links(html: str, base: str):
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    links = []
    for h in hrefs:
        if '.xlsx' in h.lower() or '.xls' in h.lower() or '.csv' in h.lower():
            links.append(urljoin(base, h))
    # unique preserving order
    out = []
    seen = set()
    for l in links:
        if l not in seen:
            out.append(l)
            seen.add(l)
    return out


def filename_from_url(url: str) -> str:
    return url.split('/')[-1].split('?')[0]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = []

    chosen = []
    for page in PAGES:
        r = requests.get(page, timeout=60)
        r.raise_for_status()
        links = extract_links(r.text, page)
        # pick preferred first, else first candidate
        pick = None
        for l in links:
            if filename_from_url(l) in PREFERRED:
                pick = l
                break
        if not pick and links:
            pick = links[0]
        report.append({'page': page, 'candidates': links, 'picked': pick})
        if pick:
            chosen.append(pick)

    # de-dup and download
    dled = []
    for url in dict.fromkeys(chosen):
        fn = filename_from_url(url)
        out = OUT / fn
        rr = requests.get(url, timeout=90)
        rr.raise_for_status()
        out.write_bytes(rr.content)
        dled.append({'url': url, 'file': str(out), 'bytes': len(rr.content)})

    summary = {'picked_count': len(chosen), 'downloaded': dled, 'pages': report}
    REPORT.write_text(json.dumps(summary, indent=2))
    print('Downloaded files:')
    for x in dled:
        print('-', Path(x['file']).name, x['bytes'])
    print('Report:', REPORT)


if __name__ == '__main__':
    main()
