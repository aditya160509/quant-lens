# Data refresh (phase 9): every Yahoo ticker, full daily history

Decided 2026-11-22. Later work: the downloader is written and tested on a sample; the full run and the loader switch are open (CHECKLIST, "Data refresh").

## Goal

Every ticker Yahoo serves (equities in every Yahoo region, ETFs, FX, crypto, futures, indices), daily bars only, as far back as Yahoo goes. Updated every day after the close.

## What we hold today (measured 2026-11-22)

- `backend/data/market_universe.parquet`: 296 MB, 4,158 tickers, 10.8M rows, one file.
- 3,548 tickers start 2014–2015 (the old download kept about 11 years). Most end 2026-01-28 to 2026-02-01.
- 2,526 names use `_` for Yahoo's `.` (`SUZLON_NS` is `SUZLON.NS`); `_IDX_X` is `^X`; `BTC_USD` is `BTC-USD`. Every renamed one tried downloads.

## What Yahoo gives (sample of 40, 2026-11-22)

| Ticker | Ours from | Yahoo from | Rows |
|---|---|---|---|
| KO, IBM | 2015 | 1962 | 2,784 → 16,332 |
| AAPL | 2015 | 1980 | 2,784 → 11,579 |
| SPY | 2015 | 1993 | 2,784 → 8,512 |
| ^GSPC | 2015 | 1927 | 2,800 → 24,841 |
| Typical .TW .KL .NS .AX | 2015 | about 2000 | about 2.5× |
| FX, futures | 2015 | 1996–2003 | about 2× |

Sample total 3.3× the rows. Screener counts (equities): US 19,851, DE 76,697 (cross-listings), TW 23,324, HK 8,582, IN 8,619, CN 7,514, GB 5,746, CA 4,664, JP 3,816, AU 3,513, KR 2,677. US ETFs 6,029. Crypto 8,037. 59 regions in all.

## Layout

```
backend/data/market/
  tickers.parquet                               ticker, yahoo, name, asset, country, exchange, currency, source
  asset=<equity|etf|index|fx|crypto|future|delisted>/country=<us|in|…|xx>/data.parquet
  _staging/                                     raw batches (resume), _no_data.txt (tickers Yahoo does not serve)
```

Each data file: date (Date), ticker, open, high, low, close, adj_close (float32), volume (float64), dividends, splits (float32); zstd level 6, sorted by ticker then date. Read it all as one table with `pl.scan_parquet("backend/data/market/asset=*/country=*/data.parquet", hive_partitioning=True)`; a filter on asset or country reads only those files.

Why split: a US run never opens the crypto or Indian files; the daily job rewrites a few small files instead of one large one; crypto (7 days) and FX (24/5) calendars stay out of the stock calendars. Float32 halves disk and memory, which is what lets 1962-onward history fit in 16 GB.

## Downloader: `backend/scripts/yahoo_market.py`

```bash
cd backend
.venv/bin/python scripts/yahoo_market.py discover                 # all regions and assets -> tickers.parquet (old names kept)
.venv/bin/python scripts/yahoo_market.py download                 # full history, resumable
.venv/bin/python scripts/yahoo_market.py build                    # staging -> the store, atomic swap per file
.venv/bin/python scripts/yahoo_market.py update                   # daily: only the days after each ticker's last stored date, then build
```

`--regions us,in`, `--assets equity,fx`, `--batch 100`, `--limit N` narrow a run. `MARKET_DIR=/some/dir` writes a scratch store (used for tests).

- **Discovery:** Yahoo screener per region × exchange (250 a page, 10,000 a query), `all_cryptocurrencies_us` for crypto, FX crosses built from 42 currencies, 52 continuous futures, 66 indices, plus every ticker in the old file under its old name.
- **Speed:** one `yf.download` call per batch of 100 with threads; measured 18–22 tickers a second. 50,000 tickers is about 45 minutes if Yahoo does not throttle.
- **Safety:** `yf.download` does not raise on HTTP 429; it logs the error and returns empty data. The script reads yfinance's error list after every batch. A rate-limit hit waits 30 s, 2 min, 10 min, then 30 min, halves the batch and retries. Clean batches grow it back by 10. Tickers with no data go to `_no_data.txt` and are skipped next time. Every batch is written as soon as it lands, so a stop loses nothing.
- **Only missing days after the first fill:** `update` reads each ticker's last stored date and asks Yahoo from there (5 days of overlap, newest download wins), one call per batch per asset/country. New tickers found since the last run get full history.
- **Why the first fill re-downloads what we already hold:** Yahoo's cost is per request, not per row. Our 2015–2026 rows and the missing pre-2015 rows come back in the same one request, so skipping held dates saves nothing; asking for the two gaps separately doubles the requests. Fresh full series also keep one consistent split and dividend adjustment instead of splicing Yahoo's onto the old file's mixed adjustment.
- **Old file:** read, never changed. Tickers Yahoo no longer serves keep their old rows in `asset=delisted`.

## Limits

- Delisted companies are gone from Yahoo, so the data stays biased toward survivors; old rows are kept.
- Yahoo publishes no rate limit; reports range from blocks after about 100 quick requests to blocks lasting a day. The data is for personal use under Yahoo's terms.
- Hourly bars only go back 730 days; 1-minute 7 days. This store is daily only.
- Some indices only serve 5 days (`^OMXS30`); they land in `_no_data.txt`.
- The old file has no asset type, so its ETFs (SPY, XLE) are filed under `asset=equity` until discovery's screener rows relabel them.
- `adj_close` for older days changes after each new dividend; `update` only appends, so run a full `download` again every few months (or compute the adjustment from the dividends and splits columns).
- Memory: a dates × symbols × 5 panel for every symbol from 1962 is about 3 GB in float64. Runs over the whole store need a start-date floor or float32 panels.

## Open steps

1. Run `discover`, `download`, `build` for everything (about 1–3 hours, longer if throttled).
2. Point `studio_v3/core/data.py` and `screener_v2/core/performance.py` at the new store (one scan with hive partitions), with a start-date floor for full-universe runs.
3. Schedule `update` after the US close; expose the freshness date (Live already reads it).
4. Data audit (DR-4) on the new store; then retire `market_universe.parquet` (backup kept).
