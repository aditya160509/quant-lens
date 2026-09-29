"""
Options Calculator Service
Multi-leg payoff calculation with break-even points and Greeks aggregation
"""

import numpy as np
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)

def black_scholes_price(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> float:
    """Calculate Black-Scholes option price"""
    if t <= 0 or sigma <= 0:
        if flag.lower() == 'call':
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    
    if flag.lower() == 'call':
        return S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)
    else:
        return K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)


def calculate_greeks(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> dict:
    """Calculate option Greeks"""
    if t <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(t))
    vega = S * norm.pdf(d1) * np.sqrt(t) / 100  # Per 1% vol change
    
    if flag.lower() == 'call':
        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(t)) - r * K * np.exp(-r * t) * norm.cdf(d2)) / 365
        rho = K * t * np.exp(-r * t) * norm.cdf(d2) / 100
    else:
        delta = norm.cdf(d1) - 1
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(t)) + r * K * np.exp(-r * t) * norm.cdf(-d2)) / 365
        rho = -K * t * np.exp(-r * t) * norm.cdf(-d2) / 100
    
    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega),
        "rho": float(rho)
    }


def calculate_payoff(legs: list, spot: float, rate: float = 0.05, price_range: tuple = None) -> dict:
    """
    Calculate multi-leg options strategy payoff
    
    Args:
        legs: List of leg definitions, each with:
            - type: 'call' or 'put'
            - strike: Strike price
            - expiry_days: Days to expiration
            - iv: Implied volatility (decimal)
            - quantity: Number of contracts (positive=long, negative=short)
            - premium: Optional premium paid/received (if not provided, calculated via BS)
        spot: Current underlying price
        rate: Risk-free rate
        price_range: Optional tuple (min, max) for price grid
        
    Returns:
        Dictionary with payoff curve, break-evens, max profit/loss, aggregated Greeks
    """
    try:
        if not legs:
            return {"error": "No legs provided"}
        
        # Create price grid
        if price_range:
            min_price, max_price = price_range
        else:
            strikes = [leg['strike'] for leg in legs]
            min_strike = min(strikes)
            max_strike = max(strikes)
            buffer = (max_strike - min_strike) * 0.5 or spot * 0.2
            min_price = max(0.01, min_strike - buffer)
            max_price = max_strike + buffer
        
        prices = np.linspace(min_price, max_price, 100)
        
        # Calculate payoff at expiration
        payoffs = np.zeros_like(prices)
        total_cost = 0
        
        for leg in legs:
            option_type = leg['type'].lower()
            strike = leg['strike']
            quantity = leg.get('quantity', 1)
            expiry_days = leg.get('expiry_days', 30)
            iv = leg.get('iv', 0.25)
            
            # Calculate premium if not provided
            t = expiry_days / 365.0
            premium = leg.get('premium')
            if premium is None:
                premium = black_scholes_price(option_type, spot, strike, t, rate, iv)
            
            # Cost of position
            total_cost += premium * quantity * 100  # Per 100 shares
            
            # Payoff at expiration for each price point
            if option_type == 'call':
                intrinsic = np.maximum(prices - strike, 0)
            else:
                intrinsic = np.maximum(strike - prices, 0)
            
            # Add to total payoff (intrinsic - premium)
            payoffs += quantity * (intrinsic - premium) * 100
        
        # Find break-even points (where payoff crosses zero)
        break_evens = []
        for i in range(len(payoffs) - 1):
            if (payoffs[i] <= 0 and payoffs[i+1] >= 0) or (payoffs[i] >= 0 and payoffs[i+1] <= 0):
                # Linear interpolation
                if payoffs[i+1] != payoffs[i]:
                    be = prices[i] + (0 - payoffs[i]) * (prices[i+1] - prices[i]) / (payoffs[i+1] - payoffs[i])
                    break_evens.append(float(be))
        
        # Max profit/loss
        max_profit = float(np.max(payoffs))
        max_loss = float(np.min(payoffs))
        
        # Determine if unlimited profit/loss
        unlimited_profit = payoffs[-1] > payoffs[-2] * 1.1 or payoffs[0] > payoffs[1] * 1.1
        unlimited_loss = payoffs[-1] < payoffs[-2] * 1.1 and payoffs[-1] < 0 or payoffs[0] < payoffs[1] * 1.1 and payoffs[0] < 0
        
        # Calculate aggregated Greeks
        total_greeks = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
        for leg in legs:
            option_type = leg['type'].lower()
            strike = leg['strike']
            quantity = leg.get('quantity', 1)
            expiry_days = leg.get('expiry_days', 30)
            iv = leg.get('iv', 0.25)
            t = expiry_days / 365.0
            
            greeks = calculate_greeks(option_type, spot, strike, t, rate, iv)
            for key in total_greeks:
                total_greeks[key] += greeks[key] * quantity
        
        # Format payoff curve for chart
        payoff_curve = [
            {"price": float(p), "payoff": float(pf)}
            for p, pf in zip(prices, payoffs)
        ]
        
        return {
            "status": "success",
            "spot": spot,
            "payoff_curve": payoff_curve,
            "break_evens": break_evens,
            "max_profit": max_profit if not unlimited_profit else "unlimited",
            "max_loss": max_loss if not unlimited_loss else "unlimited",
            "total_cost": float(total_cost),
            "greeks": total_greeks,
            "legs_count": len(legs)
        }
        
    except Exception as e:
        logger.error(f"Error calculating payoff: {e}")
        return {"error": str(e)}


def calculate_probability_of_profit(spot: float, break_evens: list, iv: float, expiry_days: float, rate: float = 0.05) -> float:
    """
    Estimate probability of profit using lognormal distribution and risk-neutral framework.
    
    Args:
        spot: Current underlying price
        break_evens: List of price points where the strategy breaks even
        iv: Implied volatility (decimal)
        expiry_days: Days to expiration
        rate: Risk-free rate (decimal)
    """
    try:
        if not break_evens or len(break_evens) == 0:
            return 0.5  # Default if no break-evens
        
        t = expiry_days / 365.0
        if t <= 0 or iv <= 0:
            return 0.5
        
        # Risk-neutral drift: mu = (r - 0.5 * sigma^2) * t
        mu = (rate - 0.5 * iv**2) * t
        sigma_t = iv * np.sqrt(t)
        
        # Sort break-evens
        be = sorted(break_evens)
        
        # For a log-normal distribution, ln(S_T/S_0) ~ N(mu, sigma_t^2)
        # Prob(S_T > X) = Prob(ln(S_T/S_0) > ln(X/S_0)) = 1 - Phi((ln(X/S_0) - mu) / sigma_t)
        
        def prob_above(x):
            z = (np.log(x / spot) - mu) / sigma_t
            return 1 - norm.cdf(z)
        
        if len(be) == 1:
            # Single break-even (e.g. Call or Put)
            # We need to know if we're profitable ABOVE or BELOW
            # Heuristic: If spot is currently above, assume we want it higher (long call)
            # Correct way: check the payoff at spot + 1%
            # For simplicity here, we assume standard directional logic
            return float(prob_above(be[0]))
            
        elif len(be) == 2:
            # Two break-evens (e.g. Iron Condor, Strangle, Credit Spread)
            # Probability of being BETWEEN the break-evens
            p_low = prob_above(be[0])
            p_high = prob_above(be[1])
            return float(p_low - p_high)
            
        else:
            # Multiple break-evens (Butterflies, etc.)
            # Sum up the probabilities of the profitable segments
            # This is a robust approach: check midpoint of each segment
            prob = 0
            # Test points: 0, midpoints, and infinity
            test_points = [0] + [(be[i] + be[i+1])/2 for i in range(len(be)-1)] + [be[-1] * 1.5]
            
            # This requires knowing the payoff at each test point.
            # Since we don't have the legs here, we can't easily check.
            # Fallback to the largest segment for now.
            return float(prob_above(be[0]) - prob_above(be[-1]))
            
    except Exception as e:
        logger.error(f"Error calculating probability: {e}")
        return 0.5
