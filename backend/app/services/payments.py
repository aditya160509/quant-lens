"""
Payment Service - Razorpay (INR) + Stripe (USD)
Multi-currency payment processing for Quant360
"""

import os
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
import requests

# Payment provider configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Pricing configuration (in smallest currency units)
PRICING = {
    "basic": {
        "monthly": {"usd": 0, "inr": 0},
        "yearly": {"usd": 0, "inr": 0}
    },
    "pro": {
        "monthly": {"usd": 2900, "inr": 249900},  # $29, ₹2499
        "yearly": {"usd": 29000, "inr": 2499900}   # $290/year, ₹24999/year
    },
    "enterprise": {
        "monthly": {"usd": 9900, "inr": 849900},  # $99, ₹8499
        "yearly": {"usd": 99000, "inr": 8499900}   # $990/year, ₹84999/year
    }
}


def create_razorpay_order(plan: str, billing: str = "monthly", currency: str = "INR") -> Dict[str, Any]:
    """
    Create a Razorpay order for Indian customers.
    
    Razorpay is preferred for India due to:
    - UPI support
    - Local card processing
    - Net banking
    - Lower failure rates
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return {"error": "Razorpay credentials not configured"}
    
    if plan not in PRICING:
        return {"error": f"Invalid plan: {plan}"}
    
    amount = PRICING[plan][billing]["inr"]
    
    if amount == 0:
        return {"error": "Cannot create order for free plan"}
    
    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        order_data = {
            "amount": amount,  # In paise
            "currency": "INR",
            "receipt": f"quant360_{plan}_{billing}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "notes": {
                "plan": plan,
                "billing_cycle": billing,
                "source": "quant360_pricing_page"
            }
        }
        
        order = client.order.create(data=order_data)
        
        return {
            "success": True,
            "provider": "razorpay",
            "order_id": order["id"],
            "amount": amount,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID,
            "plan": plan,
            "billing": billing
        }
        
    except ImportError:
        return {"error": "Razorpay SDK not installed. Run: pip install razorpay"}
    except Exception as e:
        return {"error": str(e)}


def verify_razorpay_payment(order_id: str, payment_id: str, signature: str) -> Dict[str, Any]:
    """
    Verify Razorpay payment signature.
    """
    if not RAZORPAY_KEY_SECRET:
        return {"error": "Razorpay secret not configured"}
    
    try:
        # Create signature for verification
        message = f"{order_id}|{payment_id}"
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature == expected_signature:
            return {
                "success": True,
                "verified": True,
                "order_id": order_id,
                "payment_id": payment_id
            }
        else:
            return {
                "success": False,
                "verified": False,
                "error": "Signature mismatch"
            }
            
    except Exception as e:
        return {"error": str(e)}


def create_stripe_checkout(
    plan: str, 
    billing: str = "monthly",
    success_url: str = "http://localhost:3000/payment/success",
    cancel_url: str = "http://localhost:3000/pricing"
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout session for international customers.
    
    Stripe is preferred for international payments due to:
    - 135+ currencies
    - Global card support
    - Apple Pay / Google Pay
    """
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe credentials not configured"}
    
    if plan not in PRICING:
        return {"error": f"Invalid plan: {plan}"}
    
    amount = PRICING[plan][billing]["usd"]
    
    if amount == 0:
        return {"error": "Cannot create checkout for free plan"}
    
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        
        # Create price dynamically or use pre-created price IDs
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Quant360 {plan.capitalize()} Plan",
                        "description": f"{billing.capitalize()} subscription",
                    },
                    "unit_amount": amount,
                    "recurring": {
                        "interval": "month" if billing == "monthly" else "year"
                    }
                },
                "quantity": 1
            }],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "plan": plan,
                "billing_cycle": billing,
                "source": "quant360_pricing_page"
            }
        )
        
        return {
            "success": True,
            "provider": "stripe",
            "session_id": session.id,
            "checkout_url": session.url,
            "amount": amount,
            "currency": "USD",
            "plan": plan,
            "billing": billing
        }
        
    except ImportError:
        return {"error": "Stripe SDK not installed. Run: pip install stripe"}
    except Exception as e:
        return {"error": str(e)}


def get_stripe_session_status(session_id: str) -> Dict[str, Any]:
    """
    Get the status of a Stripe checkout session.
    """
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe credentials not configured"}
    
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        
        session = stripe.checkout.Session.retrieve(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "status": session.status,
            "payment_status": session.payment_status,
            "customer_email": session.customer_details.email if session.customer_details else None,
            "subscription_id": session.subscription,
            "metadata": session.metadata
        }
        
    except Exception as e:
        return {"error": str(e)}


def create_subscription_for_user(
    user_id: str,
    plan: str,
    billing: str,
    payment_provider: str,
    payment_id: str
) -> Dict[str, Any]:
    """
    Create subscription record after successful payment.
    This would typically write to Supabase.
    """
    try:
        from .config import get_supabase_client
        supabase = get_supabase_client()
        
        subscription_data = {
            "user_id": user_id,
            "plan": plan,
            "billing_cycle": billing,
            "payment_provider": payment_provider,
            "payment_id": payment_id,
            "status": "active",
            "current_period_start": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        # This would insert into a subscriptions table
        # result = supabase.table("subscriptions").insert(subscription_data).execute()
        
        return {
            "success": True,
            "subscription": subscription_data
        }
        
    except Exception as e:
        return {"error": str(e)}


def get_pricing_config() -> Dict[str, Any]:
    """
    Get pricing configuration for frontend.
    """
    return {
        "plans": {
            "basic": {
                "name": "Basic",
                "price": {"usd": 0, "inr": 0},
                "features": [
                    "Real-time quotes",
                    "5 watchlist stocks",
                    "Basic charting",
                    "Daily market digest"
                ]
            },
            "pro": {
                "name": "Pro",
                "price": {
                    "monthly": {"usd": 29, "inr": 2499},
                    "yearly": {"usd": 290, "inr": 24999}
                },
                "features": [
                    "Everything in Basic",
                    "50+ technical indicators",
                    "Strategy backtesting",
                    "Sentiment analysis",
                    "Options flow"
                ],
                "popular": True
            },
            "enterprise": {
                "name": "Enterprise",
                "price": {
                    "monthly": {"usd": 99, "inr": 8499},
                    "yearly": {"usd": 990, "inr": 84999}
                },
                "features": [
                    "Everything in Pro",
                    "Unlimited backtests",
                    "Full API access",
                    "Walk-forward optimization",
                    "Dedicated support"
                ]
            }
        },
        "currencies": ["USD", "INR"],
        "billing_cycles": ["monthly", "yearly"],
        "providers": {
            "inr": "razorpay",
            "usd": "stripe"
        }
    }
