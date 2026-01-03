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


def calculate_probability_of_profit(spot: float, break_evens: list, iv: float, expiry_days: float) -> float:
    """
    Estimate probability of profit using lognormal distribution
    
    This is a simplified approximation assuming the underlying follows
    geometric Brownian motion with the given volatility.
    """
    try:
        if not break_evens or len(break_evens) == 0:
            return 0.5  # Default if no break-evens
        
        t = expiry_days / 365.0
        if t <= 0 or iv <= 0:
            return 0.5
        
        # Calculate probability of being above each break-even
        drift = -0.5 * iv**2 * t  # Risk-neutral drift
        vol_t = iv * np.sqrt(t)
        
        if len(break_evens) == 1:
            # Single break-even - probability of being above/below
            be = break_evens[0]
            z = (np.log(be / spot) - drift) / vol_t
            return float(1 - norm.cdf(z))  # Prob of being above break-even
        
        elif len(break_evens) == 2:
            # Two break-evens - probability of being between them (credit spread)
            be_low, be_high = sorted(break_evens)
            z_low = (np.log(be_low / spot) - drift) / vol_t
            z_high = (np.log(be_high / spot) - drift) / vol_t
            return float(norm.cdf(z_high) - norm.cdf(z_low))
        
        else:
            # Multiple break-evens - complex, use Monte Carlo
            return 0.5  # Placeholder
            
    except Exception as e:
        logger.error(f"Error calculating probability: {e}")
        return 0.5
