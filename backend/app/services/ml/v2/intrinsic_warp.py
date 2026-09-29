import numpy as np
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class StochasticDCF:
    def __init__(self, n_simulations=10000):
        self.n_sims = n_simulations

    def calculate_valuation_surface(self, ticker: str, data: Dict) -> Dict[str, Any]:
        """
        Calculates a 3D valuation surface across a range of Growth and WACC assumptions.
        Includes a Monte Carlo simulation for intrinsic value distribution.
        """
        try:
            fcf = data.get('fcf', 1e6)
            shares = data.get('shares', 1)
            target_price = data.get('price', 1)
            
            # Parametric uncertainty distributions
            growth_est = data.get('growth_est', 0.10)
            wacc_est = data.get('wacc_est', 0.09)
            
            # Simulation for the "Probabilistic Fair Value"
            # We use Normal distributions for growth and WACC uncertainty
            g_sims = np.random.normal(growth_est, 0.03, self.n_sims)
            w_sims = np.random.normal(wacc_est, 0.015, self.n_sims)
            t_sims = np.random.normal(0.025, 0.005, self.n_sims) # Long-term GDP terminal growth

            results = []
            for i in range(self.n_sims):
                v = self._dcf_logic(fcf, g_sims[i], t_sims[i], w_sims[i])
                results.append(v / shares)
            
            results = np.array(results)
            
            # Generate 3D Surface Data (Sensitivity Analysis)
            g_range = np.linspace(max(0.0, growth_est - 0.1), growth_est + 0.1, 30)
            w_range = np.linspace(max(0.04, wacc_est - 0.04), wacc_est + 0.04, 30)
            
            surface_values = []
            for g in g_range:
                row = []
                for w in w_range:
                    val = self._dcf_logic(fcf, g, 0.025, w) / shares
                    row.append(float(val))
                surface_values.append(row)

            return {
                'ticker': ticker,
                'current_price': target_price,
                'mean_value': float(np.mean(results)),
                'median_value': float(np.median(results)),
                'p25_value': float(np.percentile(results, 25)),
                'p75_value': float(np.percentile(results, 75)),
                'upside': float((np.median(results) / target_price - 1) * 100) if target_price > 0 else 0,
                'surface_grid': {
                    'growth_range': g_range.tolist(),
                    'wacc_range': w_range.tolist(),
                    'values': surface_values
                },
                'margin_of_safety': self._calculate_institutional_mos(data)
            }
        except Exception as e:
            logger.error(f"Error in StochasticDCF valuation: {e}")
            return {"error": str(e)}

    def _dcf_logic(self, fcf, g, tg, wacc, years=10):
        """Classic 2-Stage Discounted Cash Flow model"""
        # Convergence safety: WACC must be > Terminal Growth
        if wacc <= tg: 
            wacc = tg + 0.01
        
        pv = 0
        projected_fcf = fcf
        for y in range(1, years + 1):
            projected_fcf *= (1 + g)
            pv += projected_fcf / ((1 + wacc) ** y)
        
        # Terminal Value calculation (Gordon Growth Model)
        terminal_value = (projected_fcf * (1 + tg)) / (wacc - tg)
        pv += terminal_value / ((1 + wacc) ** years)
        return pv

    def _calculate_institutional_mos(self, data):
        """Computes institutional health ratios for the MoS Compass"""
        # Avoiding division by zero with safe defaults
        shares = data.get('shares', 1e6)
        mcap = data.get('price', 1) * shares
        fcf = data.get('fcf', 0)
        
        return {
            'fcf_yield': (fcf / mcap * 100) if mcap > 0 else 0,
            'current_ratio': data.get('current_ratio', 1.0),
            'debt_to_equity': data.get('debt_to_equity', 0),
            'roe': data.get('roe', 0) * 100, # Assume decimal to percentage
            'interest_coverage': data.get('interest_coverage', 5.0),
            'cash_to_debt': 1.0 / (data.get('debt_to_equity', 0.1) + 0.01) # Proxy if missing
        }
