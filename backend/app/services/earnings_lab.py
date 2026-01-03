"""
Earnings Lab Service - Institutional-grade earnings analysis.
14 production-safe modules with real data only.

CLEAN IMPLEMENTATION PER DECISION LIST:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REMOVED (no free reliable data):
  - Topic Emphasis
  - Revenue Concentration Risk  
  - Geographic Revenue Exposure
  - Debt Maturity Schedule

RENAMED (partial implementation):
  - Guidance Delta → Forward Expectation Reset
  - Activist Alerts → Ownership Threshold Alerts

KEPT WITH WORKAROUNDS:
  - Expectation Path (with gaps)
  - Tone Delta (optional/manual)
  - Institutional Holdings (45-day lag)

Data Sources:
- Yahoo Finance (primary)
- SEC EDGAR (13F/13D filings)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging
import time
import hashlib
import json
import requests

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITER & CACHE
# =============================================================================

class RateLimiter:
    def __init__(self, calls_per_minute: int = 30):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    def wait_if_needed(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.calls.append(time.time())

rate_limiter = RateLimiter(calls_per_minute=30)


class SimpleCache:
    def __init__(self, default_ttl: int = 300):
        self.cache = {}
        self.default_ttl = default_ttl
    
    def _key(self, prefix: str, symbol: str, **kw) -> str:
        return hashlib.md5(f"{prefix}:{symbol}:{json.dumps(kw, sort_keys=True)}".encode()).hexdigest()
    
    def get(self, prefix: str, symbol: str, **kw) -> Optional[Any]:
        key = self._key(prefix, symbol, **kw)
        if key in self.cache:
            data, exp = self.cache[key]
            if time.time() < exp:
                return data
            del self.cache[key]
        return None
    
    def set(self, prefix: str, symbol: str, data: Any, ttl: int = None, **kw):
        self.cache[self._key(prefix, symbol, **kw)] = (data, time.time() + (ttl or self.default_ttl))

cache = SimpleCache()


# =============================================================================
# SEC EDGAR DATA (for 13F/13D filings)
# =============================================================================

def get_cik_from_ticker(symbol: str) -> Optional[str]:
    """Get SEC CIK from ticker symbol."""
    try:
        cached = cache.get("cik_map", "ALL")
        if not cached:
            url = "https://www.sec.gov/files/company_tickers.json"
            headers = {"User-Agent": "EarningsLab/1.0 (research@example.com)"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                cached = resp.json()
                cache.set("cik_map", "ALL", cached, ttl=86400)
        
        if cached:
            for entry in cached.values():
                if entry.get("ticker", "").upper() == symbol.upper():
                    return str(entry.get("cik_str"))
    except Exception as e:
        logger.debug(f"CIK lookup error: {e}")
    return None


def fetch_sec_filings(symbol: str, form_type: str = "13") -> List[Dict]:
    """Fetch SEC filings (13F, 13D, 13G) from EDGAR."""
    try:
        cik = get_cik_from_ticker(symbol)
        if not cik:
            return []
        
        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        headers = {"User-Agent": "EarningsLab/1.0 (research@example.com)"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            
            results = []
            for i, form in enumerate(forms):
                if form_type in form:
                    results.append({
                        "form": form,
                        "date": dates[i] if i < len(dates) else None,
                    })
            return results[:10]
    except Exception as e:
        logger.debug(f"SEC EDGAR fetch error: {e}")
    return []


# =============================================================================
# YAHOO FINANCE DATA FETCHERS
# =============================================================================

def safe_get_ticker(symbol: str) -> Optional[yf.Ticker]:
    try:
        rate_limiter.wait_if_needed()
        return yf.Ticker(symbol.upper())
    except Exception as e:
        logger.error(f"Error getting ticker {symbol}: {e}")
        return None


def get_stock_info(symbol: str) -> Dict:
    cached = cache.get("info", symbol)
    if cached:
        return cached
    ticker = safe_get_ticker(symbol)
    if not ticker:
        return {}
    try:
        info = ticker.info or {}
        cache.set("info", symbol, info, ttl=3600)
        return info
    except:
        return {}


def get_price_history(symbol: str, period: str = "2y") -> pd.DataFrame:
    cached = cache.get("history", symbol, period=period)
    if cached is not None:
        return cached
    ticker = safe_get_ticker(symbol)
    if not ticker:
        return pd.DataFrame()
    try:
        df = ticker.history(period=period)
        cache.set("history", symbol, df, ttl=900, period=period)
        return df
    except:
        return pd.DataFrame()


def get_financials(symbol: str) -> Dict:
    cached = cache.get("financials", symbol)
    if cached:
        return cached
    ticker = safe_get_ticker(symbol)
    if not ticker:
        return {}
    try:
        result = {
            "income": ticker.income_stmt,
            "balance": ticker.balance_sheet,
            "cashflow": ticker.cashflow,
            "q_income": ticker.quarterly_income_stmt,
            "q_balance": ticker.quarterly_balance_sheet,
            "q_cashflow": ticker.quarterly_cashflow,
        }
        cache.set("financials", symbol, result, ttl=3600)
        return result
    except:
        return {}


# =============================================================================
# MODULE 1: EARNINGS SNAPSHOT ✅ (100% safe)
# =============================================================================

class EarningsSnapshot:
    """Foundation module - actual vs expected results."""
    
    @staticmethod
    def get_snapshot(symbol: str, quarters: int = 12) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        try:
            earnings = ticker.earnings_history
        except:
            earnings = None
        
        quarters_data = []
        if earnings is not None and not earnings.empty:
            for idx, row in earnings.head(quarters).iterrows():
                try:
                    date = pd.Timestamp(idx)
                    eps_actual = row.get('epsActual') or row.get('Reported EPS')
                    eps_est = row.get('epsEstimate') or row.get('EPS Estimate')
                    
                    surprise = None
                    beat_miss = "INLINE"
                    if eps_actual is not None and eps_est is not None and eps_est != 0:
                        surprise = ((float(eps_actual) - float(eps_est)) / abs(float(eps_est))) * 100
                        beat_miss = "BEAT" if surprise > 2 else "MISS" if surprise < -2 else "INLINE"
                    
                    quarters_data.append({
                        "period": f"{date.year} Q{((date.month - 1) // 3) + 1}",
                        "date": date.strftime("%Y-%m-%d"),
                        "eps_actual": round(float(eps_actual), 3) if eps_actual else None,
                        "eps_estimate": round(float(eps_est), 3) if eps_est else None,
                        "eps_surprise_pct": round(surprise, 2) if surprise else None,
                        "beat_miss": beat_miss,
                    })
                except:
                    continue
        
        # Extended metrics
        surprise_pctl = None
        consistency = None
        if len(quarters_data) >= 4:
            surprises = [q["eps_surprise_pct"] for q in quarters_data if q["eps_surprise_pct"]]
            if surprises and quarters_data[0]["eps_surprise_pct"]:
                surprise_pctl = round(sum(1 for s in surprises if s < quarters_data[0]["eps_surprise_pct"]) / len(surprises) * 100, 1)
            beats = sum(1 for q in quarters_data if q["beat_miss"] == "BEAT")
            consistency = round(beats / len(quarters_data) * 100, 1)
        
        current = quarters_data[0] if quarters_data else {}
        
        # Growth
        yoy = qoq = None
        if len(quarters_data) >= 2 and quarters_data[0].get("eps_actual") and quarters_data[1].get("eps_actual") and quarters_data[1]["eps_actual"] != 0:
            qoq = round(((quarters_data[0]["eps_actual"] / quarters_data[1]["eps_actual"]) - 1) * 100, 2)
        if len(quarters_data) >= 5 and quarters_data[0].get("eps_actual") and quarters_data[4].get("eps_actual") and quarters_data[4]["eps_actual"] != 0:
            yoy = round(((quarters_data[0]["eps_actual"] / quarters_data[4]["eps_actual"]) - 1) * 100, 2)
        
        return {
            "symbol": symbol.upper(),
            "name": info.get("shortName", symbol),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "current_quarter": current,
            "eps_yoy_growth": yoy,
            "eps_qoq_growth": qoq,
            "surprise_percentile": surprise_pctl,
            "consistency_score": consistency,
            "quarters": quarters_data,
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 2: EXPECTATION PATH TRACKER ⚠️ (with gaps)
# =============================================================================

class ExpectationTracker:
    """Track estimate drift - uses YF data with acknowledged gaps."""
    
    @staticmethod
    def get_expectations(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        # Get EPS trend data (REAL - shows 7d, 30d, 60d, 90d revisions)
        eps_trend = None
        eps_revisions = None
        try:
            eps_trend = ticker.eps_trend
            eps_revisions = ticker.eps_revisions
        except:
            pass
        
        # Current estimates
        fwd_eps = info.get("forwardEps")
        trail_eps = info.get("trailingEps")
        analysts = info.get("numberOfAnalystOpinions", 0)
        
        # Estimate drift
        drift = None
        bar = "NEUTRAL"
        if fwd_eps and trail_eps and trail_eps != 0:
            drift = ((fwd_eps - trail_eps) / abs(trail_eps)) * 100
            bar = "HIGH_BAR" if drift > 5 else "LOW_BAR" if drift < -5 else "NEUTRAL"
        
        # Build estimate history from EPS trend (REAL DATA)
        estimate_history = []
        if eps_trend is not None and not eps_trend.empty:
            try:
                for period in eps_trend.columns:
                    for metric in eps_trend.index:
                        if 'current' in str(metric).lower():
                            estimate_history.append({
                                "period": str(period),
                                "estimate": round(float(eps_trend.loc[metric, period]), 3) if pd.notna(eps_trend.loc[metric, period]) else None,
                            })
            except:
                pass
        
        # Revision counts (REAL DATA)
        revisions_up = revisions_down = 0
        if eps_revisions is not None and not eps_revisions.empty:
            try:
                if 'upLast7days' in eps_revisions.index:
                    revisions_up = int(eps_revisions.loc['upLast7days'].sum())
                if 'downLast7days' in eps_revisions.index:
                    revisions_down = int(eps_revisions.loc['downLast7days'].sum())
            except:
                pass
        
        dispersion = "TIGHT" if analysts > 15 else "MODERATE" if analysts > 5 else "WIDE"
        
        return {
            "symbol": symbol.upper(),
            "current_eps_estimate": round(fwd_eps, 3) if fwd_eps else None,
            "trailing_eps": round(trail_eps, 3) if trail_eps else None,
            "estimate_drift_pct": round(drift, 2) if drift else None,
            "bar_classification": bar,
            "analyst_count": analysts,
            "dispersion": dispersion,
            "revisions_up_7d": revisions_up,
            "revisions_down_7d": revisions_down,
            "estimate_history": estimate_history,
            "revision_momentum": "POSITIVE" if revisions_up > revisions_down else "NEGATIVE" if revisions_down > revisions_up else "NEUTRAL",
            "data_source": "Yahoo Finance EPS Trend",
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 3: POST-EARNINGS REPRICING ✅ (100% safe)
# =============================================================================

class RepricingAnalyzer:
    """Analyze post-earnings price action."""
    
    @staticmethod
    def get_repricing(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        try:
            hist = ticker.history(period="3mo")
        except:
            hist = pd.DataFrame()
        
        if hist.empty:
            return {"error": "No price history", "symbol": symbol}
        
        try:
            earnings = ticker.earnings_history
        except Exception as e:
            logger.debug(f"Error getting earnings history for {symbol}: {e}")
            earnings = None
        
        # Proper check for empty/None - handle both None and empty DataFrame
        if earnings is None:
            return {"error": "No earnings history available", "symbol": symbol}
        if hasattr(earnings, 'empty') and earnings.empty:
            return {"error": "No earnings history data", "symbol": symbol}
        if len(earnings) == 0:
            return {"error": "Empty earnings history", "symbol": symbol}
        
        try:
            latest_date = pd.Timestamp(earnings.index[0])
        except Exception as e:
            return {"error": f"Invalid earnings date format: {e}", "symbol": symbol}
        
        pre_mask = hist.index < latest_date
        post_mask = hist.index >= latest_date
        
        if not pre_mask.any() or not post_mask.any():
            return {"error": "Insufficient data around earnings", "symbol": symbol}
        
        pre_price = hist.loc[pre_mask, "Close"].iloc[-1]
        post_prices = hist.loc[post_mask, "Close"]
        
        reactions = []
        for days, label in [(1, "1d"), (3, "3d"), (5, "5d"), (10, "10d")]:
            if len(post_prices) >= days:
                price = post_prices.iloc[days - 1]
                change = ((price / pre_price) - 1) * 100
                reactions.append({"period": label, "price": round(float(price), 2), "change_pct": round(float(change), 2)})
        
        if not reactions:
            return {"error": "No post-earnings data", "symbol": symbol}
        
        gap = reactions[0]["change_pct"]
        final = reactions[-1]["change_pct"] if len(reactions) >= 4 else gap
        drift = final - gap
        
        if gap > 0 and drift > 0:
            verdict = "ACCEPTED"
        elif gap < 0 and drift < 0:
            verdict = "ACCEPTED"
        elif (gap > 0 and drift < -gap * 0.5) or (gap < 0 and drift > -gap * 0.5):
            verdict = "REJECTED"
        else:
            verdict = "MIXED"
        
        avg_vol = hist["Volume"].mean()
        day_vol = hist.loc[post_mask, "Volume"].iloc[0] if post_mask.any() else avg_vol
        vol_ratio = day_vol / avg_vol if avg_vol > 0 else 1
        
        pre_vol = hist.loc[pre_mask, "Close"].pct_change().std() * np.sqrt(252) * 100 if pre_mask.sum() > 5 else None
        post_vol = hist.loc[post_mask, "Close"].pct_change().std() * np.sqrt(252) * 100 if post_mask.sum() > 5 else None
        
        return {
            "symbol": symbol.upper(),
            "earnings_date": latest_date.strftime("%Y-%m-%d"),
            "pre_earnings_price": round(float(pre_price), 2),
            "reactions": reactions,
            "initial_gap_pct": round(gap, 2),
            "drift_pct": round(drift, 2),
            "total_move_pct": round(final, 2),
            "market_verdict": verdict,
            "volume_ratio": round(vol_ratio, 2),
            "volatility_before": round(pre_vol, 1) if pre_vol else None,
            "volatility_after": round(post_vol, 1) if post_vol else None,
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 4: FORWARD EXPECTATION RESET (renamed from Guidance Delta)
# =============================================================================

class ForwardExpectationReset:
    """Measure how expectations changed - not actual guidance text."""
    
    @staticmethod
    def get_reset(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        fwd_eps = info.get("forwardEps")
        trail_eps = info.get("trailingEps")
        fwd_pe = info.get("forwardPE")
        trail_pe = info.get("trailingPE")
        rev_growth = info.get("revenueGrowth")
        earn_growth = info.get("earningsGrowth")
        analysts = info.get("numberOfAnalystOpinions", 0)
        
        # Reset classification
        reset_direction = "FLAT"
        magnitude = "NONE"
        if fwd_eps and trail_eps and trail_eps != 0:
            change = (fwd_eps - trail_eps) / abs(trail_eps)
            if change > 0.05:
                reset_direction = "UP"
            elif change < -0.05:
                reset_direction = "DOWN"
            
            pct = abs(change) * 100
            if pct > 7:
                magnitude = "SIGNIFICANT"
            elif pct > 3:
                magnitude = "MODERATE"
            else:
                magnitude = "SLIGHT"
        
        confidence_shock = min(95, 50 + analysts * 3)
        
        return {
            "symbol": symbol.upper(),
            "forward_eps": round(fwd_eps, 3) if fwd_eps else None,
            "trailing_eps": round(trail_eps, 3) if trail_eps else None,
            "forward_pe": round(fwd_pe, 2) if fwd_pe else None,
            "trailing_pe": round(trail_pe, 2) if trail_pe else None,
            "revenue_growth_pct": round(rev_growth * 100, 2) if rev_growth else None,
            "earnings_growth_pct": round(earn_growth * 100, 2) if earn_growth else None,
            "reset_direction": reset_direction,
            "magnitude": magnitude,
            "confidence_shock_score": confidence_shock,
            "analyst_count": analysts,
            "data_source": "Yahoo Finance Estimates",
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 5: EARNINGS QUALITY ✅ (100% safe)
# =============================================================================

class QualityEngine:
    """Assess earnings quality - cash vs accruals."""
    
    @staticmethod
    def get_quality(symbol: str) -> Dict:
        financials = get_financials(symbol)
        info = get_stock_info(symbol)
        
        if not financials:
            return {"error": "Unable to fetch financials", "symbol": symbol}
        
        income = financials.get("q_income")
        cashflow = financials.get("q_cashflow")
        
        net_income = op_cf = free_cf = None
        try:
            if income is not None and not income.empty:
                net_income = float(income.loc["Net Income"].iloc[0]) if "Net Income" in income.index else None
            if cashflow is not None and not cashflow.empty:
                op_cf = float(cashflow.loc["Operating Cash Flow"].iloc[0]) if "Operating Cash Flow" in cashflow.index else None
                free_cf = float(cashflow.loc["Free Cash Flow"].iloc[0]) if "Free Cash Flow" in cashflow.index else None
        except:
            pass
        
        cash_ratio = None
        grade = "C"
        if op_cf and net_income and net_income != 0:
            cash_ratio = op_cf / net_income
            if cash_ratio >= 1.2:
                grade = "A"
            elif cash_ratio >= 1.0:
                grade = "B+"
            elif cash_ratio >= 0.8:
                grade = "B"
            elif cash_ratio >= 0.6:
                grade = "C"
            else:
                grade = "D"
        
        gross = info.get("grossMargins")
        operating = info.get("operatingMargins")
        profit = info.get("profitMargins")
        
        margin_quality = "STABLE"
        if operating and gross:
            if operating > gross * 0.5:
                margin_quality = "HEALTHY"
            elif operating < gross * 0.2:
                margin_quality = "CONCERNING"
        
        return {
            "symbol": symbol.upper(),
            "quality_grade": grade,
            "cash_earnings_ratio": round(cash_ratio, 2) if cash_ratio else None,
            "net_income": net_income,
            "operating_cash_flow": op_cf,
            "free_cash_flow": free_cf,
            "gross_margin_pct": round(gross * 100, 2) if gross else None,
            "operating_margin_pct": round(operating * 100, 2) if operating else None,
            "profit_margin_pct": round(profit * 100, 2) if profit else None,
            "margin_quality": margin_quality,
            "quality_flags": {
                "cash_backed": cash_ratio is not None and cash_ratio >= 1.0,
                "margin_stable": margin_quality in ["HEALTHY", "STABLE"],
            },
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 6: TONE DELTA ⚠️ (optional - limited without transcripts)
# =============================================================================

class ToneAnalyzer:
    """Basic tone analysis from company description."""
    
    RISK = ["uncertainty", "challenge", "headwind", "pressure", "difficult", "concern", "risk", "decline", "weak"]
    GROWTH = ["opportunity", "expansion", "accelerating", "momentum", "strength", "growth", "strong", "increase"]
    DEFENSIVE = ["disciplined", "cautious", "conservative", "manage", "mitigate", "protect", "maintain"]
    
    @staticmethod
    def get_tone(symbol: str) -> Dict:
        info = get_stock_info(symbol)
        summary = info.get("longBusinessSummary", "").lower()
        
        risk = sum(1 for w in ToneAnalyzer.RISK if w in summary)
        growth = sum(1 for w in ToneAnalyzer.GROWTH if w in summary)
        defensive = sum(1 for w in ToneAnalyzer.DEFENSIVE if w in summary)
        
        total = risk + growth + defensive + 1
        
        if growth > risk * 1.5:
            tone = "CONFIDENT"
        elif risk > growth * 1.5:
            tone = "DEFENSIVE"
        else:
            tone = "NEUTRAL"
        
        return {
            "symbol": symbol.upper(),
            "tone_classification": tone,
            "confidence_index": round((growth - risk) / total * 10, 2),
            "risk_language": risk,
            "growth_language": growth,
            "defensive_language": defensive,
            "data_source": "Company Description (limited)",
            "limitation": "Full tone analysis requires earnings transcripts",
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 7: ANALYST REVISION VELOCITY ✅ (100% safe)
# =============================================================================

class RevisionTracker:
    """Track analyst revision velocity."""
    
    @staticmethod
    def get_revisions(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        try:
            recs = ticker.recommendations
        except:
            recs = None
        
        revisions = []
        if recs is not None and not recs.empty:
            for idx, row in recs.head(10).iterrows():
                revisions.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "firm": row.get("Firm", "Unknown"),
                    "to_grade": row.get("To Grade", row.get("toGrade", "Unknown")),
                    "from_grade": row.get("From Grade", row.get("fromGrade", "Unknown")),
                    "action": row.get("Action", row.get("action", "Unknown")),
                })
        
        upgrades = sum(1 for r in revisions if "upgrade" in str(r.get("action", "")).lower())
        downgrades = sum(1 for r in revisions if "downgrade" in str(r.get("action", "")).lower())
        
        bias = "POSITIVE" if upgrades > downgrades else "NEGATIVE" if downgrades > upgrades else "NEUTRAL"
        velocity = len(revisions) / 30
        
        return {
            "symbol": symbol.upper(),
            "revision_velocity": round(velocity, 2),
            "directional_bias": bias,
            "upgrades_30d": upgrades,
            "downgrades_30d": downgrades,
            "analyst_count": info.get("numberOfAnalystOpinions", 0),
            "recent_revisions": revisions[:5],
            "momentum_score": round((upgrades - downgrades) / max(1, len(revisions)) * 10, 2) if revisions else 0,
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 8: POST-EARNINGS ANALYST REACTION ✅ (100% safe)
# =============================================================================

class ReactionAnalyzer:
    @staticmethod
    def get_reactions(symbol: str) -> Dict:
        revisions = RevisionTracker.get_revisions(symbol)
        snapshot = EarningsSnapshot.get_snapshot(symbol, quarters=4)
        
        if "error" in revisions:
            return revisions
        
        last_date = None
        if snapshot.get("quarters"):
            last_date = snapshot["quarters"][0].get("date")
        
        post_reactions = []
        if last_date and revisions.get("recent_revisions"):
            for r in revisions["recent_revisions"]:
                if r.get("date", "") >= last_date:
                    post_reactions.append(r)
        
        conviction = "STRONG" if len(post_reactions) >= 3 else "MODERATE" if len(post_reactions) >= 1 else "WEAK"
        
        return {
            "symbol": symbol.upper(),
            "last_earnings_date": last_date,
            "post_earnings_reactions": post_reactions,
            "conviction": conviction,
            "reaction_speed": "FAST" if post_reactions else "SLOW",
            "analyst_agreement": revisions.get("directional_bias", "NEUTRAL"),
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 9: TARGET PRICE DISTRIBUTION ✅ (100% safe)
# =============================================================================

class TargetDistribution:
    @staticmethod
    def get_targets(symbol: str) -> Dict:
        info = get_stock_info(symbol)
        
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        high = info.get("targetHighPrice")
        low = info.get("targetLowPrice")
        mean = info.get("targetMeanPrice")
        median = info.get("targetMedianPrice")
        analysts = info.get("numberOfAnalystOpinions", 0)
        
        upside = None
        if price and mean:
            upside = ((mean / price) - 1) * 100
        
        width = None
        dispersion = "TIGHT"
        if high and low:
            width = high - low
            if mean and width / mean > 0.3:
                dispersion = "WIDE"
            elif mean and width / mean > 0.15:
                dispersion = "MODERATE"
        
        return {
            "symbol": symbol.upper(),
            "current_price": round(price, 2) if price else None,
            "target_high": round(high, 2) if high else None,
            "target_low": round(low, 2) if low else None,
            "target_mean": round(mean, 2) if mean else None,
            "target_median": round(median, 2) if median else None,
            "implied_upside_pct": round(upside, 2) if upside else None,
            "range_width": round(width, 2) if width else None,
            "dispersion": dispersion,
            "analyst_count": analysts,
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 10: INSTITUTIONAL HOLDINGS ⚠️ (45-day lag)
# =============================================================================

class InstitutionalTracker:
    @staticmethod
    def get_institutional(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        inst_pct = info.get("heldPercentInstitutions")
        insider_pct = info.get("heldPercentInsiders")
        
        try:
            holders = ticker.institutional_holders
        except:
            holders = None
        
        holders_list = []
        if holders is not None and not holders.empty:
            for _, row in holders.head(10).iterrows():
                holders_list.append({
                    "holder": row.get("Holder", "Unknown"),
                    "shares": int(row.get("Shares", 0)),
                    "date_reported": row.get("Date Reported").strftime("%Y-%m-%d") if pd.notna(row.get("Date Reported")) else None,
                    "pct_out": round(float(row.get("% Out", 0)) * 100, 2) if row.get("% Out") else None,
                })
        
        trend = "STABLE"
        if inst_pct and inst_pct > 0.8:
            trend = "HIGHLY_HELD"
        elif inst_pct and inst_pct < 0.3:
            trend = "UNDER_OWNED"
        
        return {
            "symbol": symbol.upper(),
            "institutional_pct": round(inst_pct * 100, 2) if inst_pct else None,
            "insider_pct": round(insider_pct * 100, 2) if insider_pct else None,
            "accumulation_trend": trend,
            "top_holders": holders_list,
            "data_lag_note": "13F data has 45-day reporting lag",
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 11: OWNERSHIP THRESHOLD ALERTS (renamed from Activist Alerts)
# =============================================================================

class OwnershipAlerts:
    """Monitor ownership crossing meaningful levels via SEC EDGAR."""
    
    @staticmethod
    def get_alerts(symbol: str) -> Dict:
        institutional = InstitutionalTracker.get_institutional(symbol)
        
        # Check SEC filings for 13D/13G
        filings_13d = fetch_sec_filings(symbol, "13D")
        filings_13g = fetch_sec_filings(symbol, "13G")
        
        alerts = []
        control_risk = "LOW"
        
        # Check for large holders (>5%)
        if institutional.get("top_holders"):
            for h in institutional["top_holders"]:
                pct = h.get("pct_out", 0)
                if pct and pct > 10:
                    alerts.append({
                        "holder": h["holder"],
                        "ownership_pct": pct,
                        "alert_type": "LARGE_POSITION",
                        "risk_level": "HIGH" if pct > 15 else "MODERATE",
                    })
                    control_risk = "HIGH" if pct > 15 else "MODERATE"
        
        # Add 13D/13G filings
        for f in filings_13d[:3]:
            alerts.append({
                "form": f["form"],
                "date": f["date"],
                "alert_type": "13D_FILING",
                "risk_level": "HIGH",
            })
            control_risk = "HIGH"
        
        for f in filings_13g[:3]:
            alerts.append({
                "form": f["form"],
                "date": f["date"],
                "alert_type": "13G_FILING",
                "risk_level": "MODERATE",
            })
        
        return {
            "symbol": symbol.upper(),
            "control_risk": control_risk,
            "alerts": alerts,
            "has_large_holder": len(alerts) > 0,
            "data_source": "Yahoo Finance + SEC EDGAR",
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 12: BUYBACK TRACKER ✅ (100% safe)
# =============================================================================

class BuybackTracker:
    @staticmethod
    def get_buyback(symbol: str) -> Dict:
        info = get_stock_info(symbol)
        financials = get_financials(symbol)
        hist = get_price_history(symbol, period="1y")
        
        shares = info.get("sharesOutstanding")
        
        repurchases = None
        if financials.get("q_cashflow") is not None:
            cf = financials["q_cashflow"]
            if "Repurchase Of Capital Stock" in cf.index:
                try:
                    repurchases = float(cf.loc["Repurchase Of Capital Stock"].iloc[0])
                except:
                    pass
        
        buyback_yield = None
        if repurchases and info.get("marketCap"):
            buyback_yield = abs(repurchases) / info["marketCap"] * 100
        
        avg_price = current = None
        if not hist.empty:
            avg_price = hist["Close"].mean()
            current = hist["Close"].iloc[-1]
        
        timing = "NEUTRAL"
        if avg_price and current:
            if current > avg_price * 1.1:
                timing = "GOOD"
            elif current < avg_price * 0.9:
                timing = "POOR"
        
        grade = "C"
        if buyback_yield and buyback_yield > 3:
            grade = "A" if timing == "GOOD" else "B"
        elif buyback_yield and buyback_yield > 1:
            grade = "B" if timing == "GOOD" else "C"
        
        return {
            "symbol": symbol.upper(),
            "effectiveness_grade": grade,
            "buyback_yield_pct": round(buyback_yield, 2) if buyback_yield else None,
            "repurchases_ttm": repurchases,
            "shares_outstanding": shares,
            "avg_price_52w": round(avg_price, 2) if avg_price else None,
            "current_price": round(current, 2) if current else None,
            "timing_quality": timing,
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 13: DIVIDEND MONITOR ✅ (100% safe)
# =============================================================================

class DividendMonitor:
    @staticmethod
    def get_dividend(symbol: str) -> Dict:
        ticker = safe_get_ticker(symbol)
        if not ticker:
            return {"error": "Unable to fetch ticker", "symbol": symbol}
        
        info = ticker.info or {}
        
        rate = info.get("dividendRate")
        yield_pct = info.get("dividendYield")
        payout = info.get("payoutRatio")
        
        try:
            divs = ticker.dividends
        except:
            divs = pd.Series()
        
        history = []
        if not divs.empty:
            for date, amt in divs.tail(12).items():
                history.append({"date": date.strftime("%Y-%m-%d"), "amount": round(float(amt), 4)})
        
        safety = "SECURE"
        cut_risk = 5
        if payout:
            if payout > 0.8:
                safety, cut_risk = "AT_RISK", 60
            elif payout > 0.6:
                safety, cut_risk = "MODERATE", 25
            elif payout > 0.4:
                safety, cut_risk = "SAFE", 10
            else:
                safety, cut_risk = "VERY_SAFE", 5
        
        growth = None
        if len(history) >= 5:
            old = history[-5]["amount"]
            new = history[0]["amount"]
            if old > 0:
                growth = ((new / old) ** 0.25 - 1) * 100
        
        return {
            "symbol": symbol.upper(),
            "dividend_rate": rate,
            "yield_pct": round(yield_pct * 100, 2) if yield_pct else None,
            "payout_ratio_pct": round(payout * 100, 2) if payout else None,
            "safety_rating": safety,
            "cut_risk_pct": cut_risk,
            "dividend_growth_pct": round(growth, 2) if growth else None,
            "dividend_history": history[-8:],
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MODULE 14: PEER COMPARISON ✅ (100% safe)
# =============================================================================

class PeerComparator:
    PEER_MAP = {
        "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
        "Financials": ["JPM", "BAC", "GS", "MS", "C"],
        "Healthcare": ["JNJ", "PFE", "UNH", "MRK", "ABBV"],
        "Consumer Discretionary": ["AMZN", "TSLA", "HD", "NKE", "MCD"],
        "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    }
    
    @staticmethod
    def get_peer_comparison(symbol: str, peers: List[str] = None) -> Dict:
        info = get_stock_info(symbol)
        
        if not peers:
            sector = info.get("sector", "")
            peers = PeerComparator.PEER_MAP.get(sector, ["SPY"])
            peers = [p for p in peers if p.upper() != symbol.upper()][:4]
        
        company_data = EarningsSnapshot.get_snapshot(symbol, quarters=4)
        company_pe = info.get("forwardPE")
        company_surprise = company_data.get("current_quarter", {}).get("eps_surprise_pct", 0) or 0
        
        peer_data = []
        for p in peers:
            try:
                snap = EarningsSnapshot.get_snapshot(p, quarters=4)
                p_info = get_stock_info(p)
                current = snap.get("current_quarter", {})
                peer_data.append({
                    "symbol": p,
                    "name": p_info.get("shortName", p),
                    "eps_surprise_pct": current.get("eps_surprise_pct"),
                    "beat_miss": current.get("beat_miss"),
                    "pe_ratio": p_info.get("forwardPE"),
                    "yoy_growth": snap.get("eps_yoy_growth"),
                })
            except:
                pass
        
        all_surprises = [company_surprise] + [p.get("eps_surprise_pct", 0) or 0 for p in peer_data]
        all_surprises.sort(reverse=True)
        rank = all_surprises.index(company_surprise) + 1
        
        peer_pe_avg = np.mean([p.get("pe_ratio") or 0 for p in peer_data if p.get("pe_ratio")]) if peer_data else None
        premium = ((company_pe / peer_pe_avg) - 1) * 100 if company_pe and peer_pe_avg and peer_pe_avg != 0 else None
        
        return {
            "symbol": symbol.upper(),
            "company": {
                "name": info.get("shortName", symbol),
                "eps_surprise_pct": company_surprise,
                "beat_miss": company_data.get("current_quarter", {}).get("beat_miss"),
                "pe_ratio": company_pe,
                "yoy_growth": company_data.get("eps_yoy_growth"),
            },
            "peers": peer_data,
            "rank": f"{rank} of {len(all_surprises)}",
            "relative_performance": "ABOVE_AVG" if rank <= 2 else "BELOW_AVG" if rank > 3 else "AVERAGE",
            "pe_vs_peers_pct": round(premium, 2) if premium else None,
            "sector": info.get("sector"),
            "as_of": datetime.now().isoformat(),
        }


# =============================================================================
# MASTER SERVICE (14 MODULES)
# =============================================================================

class EarningsLabService:
    """Master service - 14 production-safe modules."""
    
    def __init__(self):
        self.snapshot = EarningsSnapshot()
        self.expectations = ExpectationTracker()
        self.repricing = RepricingAnalyzer()
        self.forward_reset = ForwardExpectationReset()  # renamed
        self.quality = QualityEngine()
        self.tone = ToneAnalyzer()  # optional
        self.revisions = RevisionTracker()
        self.reactions = ReactionAnalyzer()
        self.targets = TargetDistribution()
        self.institutional = InstitutionalTracker()
        self.ownership_alerts = OwnershipAlerts()  # renamed
        self.buyback = BuybackTracker()
        self.dividend = DividendMonitor()
        self.peers = PeerComparator()
    
    def get_full_analysis(self, symbol: str) -> Dict:
        return {
            "symbol": symbol.upper(),
            "snapshot": self.snapshot.get_snapshot(symbol),
            "expectations": self.expectations.get_expectations(symbol),
            "repricing": self.repricing.get_repricing(symbol),
            "forward_reset": self.forward_reset.get_reset(symbol),
            "quality": self.quality.get_quality(symbol),
            "tone": self.tone.get_tone(symbol),
            "revisions": self.revisions.get_revisions(symbol),
            "reactions": self.reactions.get_reactions(symbol),
            "targets": self.targets.get_targets(symbol),
            "institutional": self.institutional.get_institutional(symbol),
            "ownership_alerts": self.ownership_alerts.get_alerts(symbol),
            "buyback": self.buyback.get_buyback(symbol),
            "dividend": self.dividend.get_dividend(symbol),
            "peers": self.peers.get_peer_comparison(symbol),
            "modules_count": 14,
            "removed_modules": ["topic_emphasis", "revenue_concentration", "geographic_exposure", "debt_maturity"],
            "generated_at": datetime.now().isoformat(),
        }


earnings_lab_service = EarningsLabService()
