"""
Payment API Endpoints
Handles checkout creation and payment verification
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import os
import hmac
import hashlib

from ..services import payments
from ..auth.dependencies import get_current_user, get_optional_user, CurrentUser

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str  # basic, pro, enterprise
    billing: str = "monthly"  # monthly or yearly
    currency: str = "USD"  # USD or INR


class RazorpayVerifyRequest(BaseModel):
    order_id: str
    payment_id: str
    signature: str


class StripeVerifyRequest(BaseModel):
    session_id: str


@router.get("/payments/config")
async def get_payment_config():
    """
    Get pricing configuration.
    No authentication required - this is public info.
    """
    config = payments.get_pricing_config()
    
    # Add payment gateway availability
    config["razorpay_enabled"] = bool(os.getenv("RAZORPAY_KEY_ID"))
    config["stripe_enabled"] = bool(os.getenv("STRIPE_SECRET_KEY"))
    config["razorpay_key_id"] = os.getenv("RAZORPAY_KEY_ID", "")
    config["stripe_publishable_key"] = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    
    return config


@router.post("/payments/checkout")
async def create_checkout(
    request: CheckoutRequest,
    user: Optional[CurrentUser] = Depends(get_optional_user)
):
    """
    Create a checkout session.
    
    - INR payments go through Razorpay
    - USD/other payments go through Stripe
    """
    if request.plan == "basic":
        return {"success": True, "message": "Basic plan is free. No payment needed."}
    
    if request.plan not in ["pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    if request.billing not in ["monthly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid billing cycle")
    
    # Route to appropriate payment provider
    if request.currency.upper() == "INR":
        result = payments.create_razorpay_order(
            plan=request.plan,
            billing=request.billing
        )
    else:
        # Default to Stripe for USD and other currencies
        base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        result = payments.create_stripe_checkout(
            plan=request.plan,
            billing=request.billing,
            success_url=f"{base_url}/payment/success",
            cancel_url=f"{base_url}/pricing"
        )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/payments/verify/razorpay")
async def verify_razorpay_payment(
    request: RazorpayVerifyRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Verify Razorpay payment after customer completes payment.
    """
    result = payments.verify_razorpay_payment(
        order_id=request.order_id,
        payment_id=request.payment_id,
        signature=request.signature
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    if result.get("verified"):
        # Create subscription record
        # This would update the user's subscription in Supabase
        return {
            "success": True,
            "message": "Payment verified successfully",
            "payment_id": request.payment_id
        }
    
    raise HTTPException(status_code=400, detail="Payment verification failed")


@router.post("/payments/verify/stripe")
async def verify_stripe_payment(
    request: StripeVerifyRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Verify Stripe payment using session ID.
    """
    result = payments.get_stripe_session_status(request.session_id)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    if result.get("payment_status") == "paid":
        return {
            "success": True,
            "message": "Payment verified successfully",
            "subscription_id": result.get("subscription_id"),
            "plan": result.get("metadata", {}).get("plan"),
            "billing": result.get("metadata", {}).get("billing_cycle")
        }
    
    return {
        "success": False,
        "status": result.get("payment_status"),
        "message": "Payment not yet completed"
    }


@router.get("/payments/subscription")
async def get_user_subscription(
    user: CurrentUser = Depends(get_current_user)
):
    """
    Get current user's subscription status.
    """
    # TODO: Fetch from Supabase subscriptions table
    # For now, return a placeholder
    return {
        "user_id": user.id,
        "plan": "free",
        "status": "active",
        "billing_cycle": None,
        "current_period_end": None
    }


@router.post("/payments/webhook/razorpay")
async def razorpay_webhook(request: Request):
    """
    Handle Razorpay webhooks for subscription events.
    """
    # Verify webhook signature
    signature = request.headers.get("X-Razorpay-Signature", "")
    body = await request.body()
    
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if webhook_secret:
        expected = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected:
            raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Process webhook event
    # event = await request.json()
    # Handle events like: payment.captured, subscription.activated, etc.
    
    return {"status": "ok"}


@router.post("/payments/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks for subscription events.
    """
    import stripe
    
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        import json
        event = json.loads(payload)
    
    # Handle specific events
    event_type = event.get("type", "")
    
    if event_type == "checkout.session.completed":
        # Payment successful - activate subscription
        session = event["data"]["object"]
        # Update user subscription in database
        pass
    
    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled - downgrade to free
        pass
    
    elif event_type == "invoice.payment_failed":
        # Payment failed - notify user
        pass
    
    return {"status": "ok"}
