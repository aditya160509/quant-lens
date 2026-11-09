# Studio research, November 2026

Researched 2026-11-09 with TinyFish fetch on vendor pages and licence files. Method follows `2026-11-screener-competitors.md` and `2026-11-screener-open-source.md`. Marks: **[official]** read on the vendor page or repo in this session; **[memory]** from earlier knowledge, not re-read today; **[unverified]** could not be confirmed.

## 1. Paid research and backtest IDEs

### TradingView (Pine Script)
Source: https://www.tradingview.com/pricing/ **[official]**; Pine strategy docs and Deep Backtesting help pages **[official]** (fetched 2026-11-09).

| Item | Finding |
|---|---|
| Tiers | Free $0; $12.95, $29.95, $59.95, $199.95 per month (listed as special prices, annual saving shown) |
| Alerts by tier | 20, 100, 400 and 1,000 price alerts with matching technical alerts; multi-condition alerts; alerts that do not expire; watchlist alerts from the second tier up |
| Pine strategies | `strategy()` declaration sets capital, commission, slippage, pyramiding, margin, order size and bar-close execution defaults. Users override in the Properties tab |
| Fill model | Market orders fill on the same closing tick the script creates them, by default (**[official]**). Commission and slippage are inputs, not assumptions hidden in the engine |
| Deep Backtesting | Separate mode that keeps every closed trade and does not trim orders from the report; its trade list is downloadable |
| Gaps for us | Proprietary language, no free-standing data export of the Studio kind, alerts run on TradingView's servers |

### QuantConnect (LEAN)
Source: https://www.quantconnect.com/pricing/ **[official]** (tier names and limits read; dollar amounts were not extracted, so prices are **[unverified]**).

| Item | Finding |
|---|---|
| Tiers | Free Plan, Quant Researcher, Team, Trading Firm, Institution |
| Free plan | Equity, indexes, forex, crypto, futures and options data; unlimited backtesting in the cloud; 1 backtest node; 10 KB log limit; 10K orders per backtest; 25 data imports per backtest |
| Quant Researcher | Local coding (VSCode and CLI), expanded data, 2 compute nodes, 100 KB logs, 10M orders, 100 imports, backtest PDF report |
| Team | Project collaboration, 10 users, 10 nodes, 1 MB logs, 250 imports |
| Institution | On-premises platform, FIX brokerages, AES-256 code encryption, unlimited limits |
| Licence of engine | LEAN is Apache-2.0 **[official]**, from the repo LICENSE fetched 2026-11-09 |
| Gaps for us | Code-first (C# and Python) and heavy to run locally; a full engine we do not need |

### Others (not re-read today)
- **Portfolio123**: covered in the Screener review (section 3). **[third party, via Screener review]**
- **Koyfin, Stock Rover, Fiscal.ai**: data and screening tools; not backtest IDEs; not used for Studio parity. **[memory]**
- **NinjaTrader, MetaTrader, AmiBroker**: desktop backtest platforms with proprietary languages; out of scope for a browser product. **[memory]**
- **Composer, Trade Ideas, Tradovate**: not fetched; **[unverified]** and not used for any mark in the review.

## 2. Open-source libraries, licences

| Library | Licence | Mark | Source |
|---|---|---|---|
| QuantConnect LEAN | Apache-2.0 | **[official]** | github.com/QuantConnect/Lean LICENSE |
| backtrader | GPL-3.0 | **[official]** | raw LICENSE, fetched 2026-11-09. Copyleft: ideas only |
| backtesting.py | AGPL-3.0 | **[memory]** raw LICENSE returned 404 on master; not re-confirmed. Copyleft: ideas only |
| vectorbt (open source) | Apache-2.0 | **[unverified]** raw LICENSE fetch did not return text. Re-check before any adoption |
| TA-Lib | BSD | **[memory]** and Screener open-source reference |
| lightweight-charts (TradingView) | Apache-2.0 | **[memory]** and already installed (5.1) per Screener open-source reference |
| Monaco editor | MIT | **[memory]**, already used by `Editor.jsx` |
| @pierre/diffs, @pierre/trees | Apache-2.0 | **[memory]** and PLAN section 5 |
| DuckDB | MIT | Screener open-source reference |
| Typst | Apache-2.0 | **[memory]**, to confirm before adoption |
| scipy (SLSQP already used by portfolio.py) | BSD | **[memory]**; read in code: `services/studio/portfolio.py` imports `scipy.optimize.minimize` |

Rules used (same as the Screener review): no GPL, AGPL, SSPL or unlicensed code in anything we ship. Copyleft projects are ideas only.

## 3. Unverified in this review
- QuantConnect dollar prices.
- vectorbt and backtesting.py licence text (see table).
- Typst licence.
- Competitor tiers beyond TradingView and QuantConnect.
