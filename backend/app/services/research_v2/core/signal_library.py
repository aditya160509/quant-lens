"""Classic anomalies written in the signal formula language.

``expected_sign`` is the sign of the published premium for the formula as
written (+1: high value earns higher returns; -1: high value earns lower returns).
"""

from __future__ import annotations

_L = [
    # momentum and reversal
    ("mom_12_1", "Momentum 12-1", "momentum", "delay(close, 1) / delay(close, 12) - 1", "Jegadeesh and Titman (1993)", 1993, 1),
    ("mom_6_1", "Momentum 6-1", "momentum", "delay(close, 1) / delay(close, 6) - 1", "Jegadeesh and Titman (1993)", 1993, 1),
    ("mom_intermediate", "Intermediate momentum (t-12 to t-7)", "momentum", "delay(close, 7) / delay(close, 12) - 1", "Novy-Marx (2012)", 2012, 1),
    ("mom_sector_adj", "Sector-neutral momentum 12-1", "momentum", "neutralize(delay(close, 1) / delay(close, 12) - 1, sector)", "Moskowitz and Grinblatt (1999)", 1999, 1),
    ("mom_52w_high", "52-week high proximity", "momentum", "close / ts_max(close, 12)", "George and Hwang (2004)", 2004, 1),
    ("mom_consistency", "Return consistency (share of up months, 12m)", "momentum", "ts_mean(if_else(returns > 0, 1, 0), 12)", "Grinblatt and Moskowitz (2004)", 2004, 1),
    ("str_1m", "Short-term reversal (1m)", "reversal", "returns", "Jegadeesh (1990)", 1990, -1),
    ("str_2m", "Two-month reversal", "reversal", "ts_sum(returns, 2)", "Lehmann (1990)", 1990, -1),
    ("ltr_36_12", "Long-term reversal (t-36 to t-12)", "reversal", "delay(close, 12) / delay(close, 36) - 1", "De Bondt and Thaler (1985)", 1985, -1),
    # risk
    ("ivol", "Idiosyncratic volatility", "risk", "ivol", "Ang, Hodrick, Xing and Zhang (2006)", 2006, -1),
    ("rvol_daily", "Realised volatility (daily, 1m)", "risk", "rvol", "Ang, Hodrick, Xing and Zhang (2006)", 2006, -1),
    ("vol_12m", "Return volatility (12m)", "risk", "ts_std(returns, 12)", "Ang, Hodrick, Xing and Zhang (2006)", 2006, -1),
    ("maxret", "Maximum daily return (lottery demand)", "risk", "maxret", "Bali, Cakici and Whitelaw (2011)", 2011, -1),
    ("maxret_avg", "Average of monthly max daily return (12m)", "risk", "ts_mean(maxret, 12)", "Bali, Cakici and Whitelaw (2011)", 2011, -1),
    ("beta", "Market beta", "risk", "beta", "Frazzini and Pedersen (2014)", 2014, -1),
    ("downside_range", "Worst month in 12m", "risk", "ts_min(returns, 12)", "Ang, Chen and Xing (2006)", 2006, 1),
    ("vol_of_vol", "Volatility of volatility", "risk", "ts_std(rvol, 12)", "Baltussen, van Bekkum and van der Grient (2018)", 2018, -1),
    # liquidity and size
    ("size", "Size (log market cap)", "size", "log(mcap)", "Banz (1981)", 1981, -1),
    ("amihud", "Illiquidity (Amihud)", "liquidity", "amihud_d", "Amihud (2002)", 2002, 1),
    ("amihud_12m", "Illiquidity (Amihud, 12m average)", "liquidity", "ts_mean(amihud_d, 12)", "Amihud (2002)", 2002, 1),
    ("turnover", "Share turnover", "liquidity", "volume / shares", "Datar, Naik and Radcliffe (1998)", 1998, -1),
    ("dollar_volume", "Dollar trading volume (log)", "liquidity", "log(dollar_volume)", "Brennan, Chordia and Subrahmanyam (1998)", 1998, -1),
    ("volume_trend", "Volume trend (3m vs 12m)", "liquidity", "ts_mean(volume, 3) / ts_mean(volume, 12)", "Gervais, Kaniel and Mingelgrin (2001)", 2001, 1),
    ("price_level", "Share price level (log)", "liquidity", "log(close)", "Blume and Husic (1973)", 1973, -1),
    # value
    ("bm", "Book-to-market", "value", "equity / mcap", "Fama and French (1992)", 1992, 1),
    ("bm_sector_adj", "Sector-adjusted book-to-market", "value", "neutralize(equity / mcap, sector)", "Cohen and Polk (1998)", 1998, 1),
    ("ep", "Earnings-to-price", "value", "net_income / mcap", "Basu (1977)", 1977, 1),
    ("sp", "Sales-to-price", "value", "revenue / mcap", "Barbee, Mukherji and Raines (1996)", 1996, 1),
    ("cfp", "Cash flow-to-price", "value", "op_cash_flow / mcap", "Lakonishok, Shleifer and Vishny (1994)", 1994, 1),
    ("fcf_yield", "Free cash flow yield", "value", "free_cash_flow / mcap", "Lakonishok, Shleifer and Vishny (1994)", 1994, 1),
    ("ebitda_ev", "EBITDA-to-enterprise value", "value", "ebitda / (mcap + debt - cash)", "Loughran and Wellman (2011)", 2011, 1),
    ("div_yield", "Dividend yield", "value", "abs(dividends_paid) / mcap", "Fama and French (1988)", 1988, 1),
    ("tangible_bm", "Tangible book-to-market", "value", "tangible_book / mcap", "Daniel and Titman (2006)", 2006, 1),
    # profitability and quality
    ("gp_a", "Gross profitability", "profitability", "gross_profit / assets", "Novy-Marx (2013)", 2013, 1),
    ("roe", "Return on equity", "profitability", "net_income / equity", "Haugen and Baker (1996)", 1996, 1),
    ("roa", "Return on assets", "profitability", "net_income / assets", "Haugen and Baker (1996)", 1996, 1),
    ("op_profit_be", "Operating profitability to book equity", "profitability", "operating_income / equity", "Fama and French (2015)", 2015, 1),
    ("gross_margin", "Gross margin", "profitability", "gross_profit / revenue", "Novy-Marx (2013)", 2013, 1),
    ("asset_turnover", "Asset turnover", "profitability", "revenue / assets", "Soliman (2008)", 2008, 1),
    ("cash_profit", "Cash-based operating profitability", "profitability", "(gross_profit - delta(receivables, 12) - delta(inventory, 12)) / assets", "Ball, Gerakos, Linnainmaa and Nikolaev (2016)", 2016, 1),
    ("earnings_change", "Change in earnings scaled by assets", "profitability", "delta(net_income, 12) / assets", "Ball and Brown (1968)", 1968, 1),
    # investment and growth
    ("asset_growth", "Asset growth", "investment", "assets / delay(assets, 12) - 1", "Cooper, Gulen and Schill (2008)", 2008, -1),
    ("ppe_growth", "PP&E growth", "investment", "ppe / delay(ppe, 12) - 1", "Titman, Wei and Xie (2004)", 2004, -1),
    ("inventory_growth", "Inventory growth", "investment", "inventory / delay(inventory, 12) - 1", "Thomas and Zhang (2002)", 2002, -1),
    ("sales_growth", "Sales growth", "investment", "revenue / delay(revenue, 12) - 1", "Lakonishok, Shleifer and Vishny (1994)", 1994, -1),
    ("net_issuance", "Net share issuance (12m)", "investment", "log(shares / delay(shares, 12))", "Pontiff and Woodgate (2008)", 2008, -1),
    ("capex_to_assets", "Capital expenditure to assets", "investment", "abs(capex) / assets", "Titman, Wei and Xie (2004)", 2004, -1),
    # accruals, leverage, intangibles
    ("accruals", "Accruals (Sloan)", "accruals", "(net_income - op_cash_flow) / assets", "Sloan (1996)", 1996, -1),
    ("leverage", "Leverage (debt-to-assets)", "leverage", "debt / assets", "Bhandari (1988)", 1988, 1),
    ("cash_holdings", "Cash holdings", "leverage", "cash / assets", "Palazzo (2012)", 2012, 1),
    ("current_ratio", "Current ratio", "leverage", "current_assets / current_liabilities", "Ou and Penman (1989)", 1989, 1),
    ("rd_mcap", "R&D to market cap", "intangibles", "rd_expense / mcap", "Chan, Lakonishok and Sougiannis (2001)", 2001, 1),
    ("rd_sales", "R&D to sales", "intangibles", "rd_expense / revenue", "Chan, Lakonishok and Sougiannis (2001)", 2001, 1),
    ("sga_sales", "SG&A to sales (organisation capital)", "intangibles", "sga / revenue", "Eisfeldt and Papanikolaou (2013)", 2013, 1),
]

LIBRARY = [{"id": a, "name": b, "category": c, "formula": d, "citation": e, "year": f, "expected_sign": g} for a, b, c, d, e, f, g in _L]
BY_ID = {x["id"]: x for x in LIBRARY}
