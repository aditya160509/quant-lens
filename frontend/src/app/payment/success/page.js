'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'

function PaymentSuccessContent() {
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session_id')
  // If no sessionId, assume Razorpay callback success
  const [status, setStatus] = useState(sessionId ? 'loading' : 'success')
  const [subscription, setSubscription] = useState(null)


  useEffect(() => {
    if (!sessionId) return
    
    // Verify Stripe payment
    fetch('/api/payments/verify/stripe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setStatus('success')
          setSubscription(data)
        } else {
          setStatus('pending')
        }
      })
      .catch(() => setStatus('error'))
  }, [sessionId])

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #030608 0%, #0a0f18 100%)',
      padding: '20px'
    }}>
      <div style={{
        maxWidth: '500px',
        width: '100%',
        textAlign: 'center'
      }}>
        {status === 'loading' && (
          <>
            <div style={{
              width: '64px',
              height: '64px',
              border: '3px solid rgba(255, 214, 10, 0.3)',
              borderTopColor: '#ffd60a',
              borderRadius: '50%',
              margin: '0 auto 24px',
              animation: 'spin 1s linear infinite'
            }} />
            <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            <h1 style={{ color: '#e0e6ed', fontSize: '24px', fontWeight: 700 }}>
              Verifying payment...
            </h1>
          </>
        )}

        {status === 'success' && (
          <>
            <div style={{
              width: '80px',
              height: '80px',
              background: 'linear-gradient(135deg, rgba(0, 255, 136, 0.2) 0%, rgba(0, 255, 136, 0.1) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
              fontSize: '40px',
              border: '2px solid rgba(0, 255, 136, 0.4)'
            }}>
              ✓
            </div>
            <h1 style={{
              color: '#00ff88',
              fontSize: '32px',
              fontWeight: 700,
              marginBottom: '12px'
            }}>
              Welcome to Pro!
            </h1>
            <p style={{
              color: '#8b9ab0',
              fontSize: '16px',
              marginBottom: '32px',
              lineHeight: 1.6
            }}>
              Your subscription is now active. You have full access to all premium features.
            </p>

            <div style={{
              background: 'rgba(10, 15, 24, 0.8)',
              border: '1px solid rgba(30, 39, 56, 0.5)',
              borderRadius: '12px',
              padding: '24px',
              marginBottom: '32px',
              textAlign: 'left'
            }}>
              <h3 style={{ color: '#ffd60a', fontSize: '14px', marginBottom: '16px' }}>
                You now have access to:
              </h3>
              <ul style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                {[
                  '50+ technical indicators',
                  'Unlimited strategy backtesting',
                  'Real-time sentiment analysis',
                  'Options flow analytics',
                  'Walk-forward optimization',
                  'Priority support'
                ].map((feature, i) => (
                  <li key={i} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    fontSize: '14px',
                    color: '#e0e6ed'
                  }}>
                    <span style={{ color: '#00ff88' }}>✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>

            <Link
              href="/portfolio"
              style={{
                display: 'inline-block',
                padding: '16px 40px',
                background: 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
                color: '#0a0f18',
                borderRadius: '12px',
                fontSize: '16px',
                fontWeight: 700,
                textDecoration: 'none'
              }}
            >
              Go to Dashboard
            </Link>
          </>
        )}

        {status === 'pending' && (
          <>
            <div style={{
              width: '80px',
              height: '80px',
              background: 'rgba(255, 214, 10, 0.1)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
              fontSize: '40px',
              border: '2px solid rgba(255, 214, 10, 0.3)'
            }}>
              ⏳
            </div>
            <h1 style={{ color: '#ffd60a', fontSize: '28px', fontWeight: 700, marginBottom: '12px' }}>
              Payment Processing
            </h1>
            <p style={{ color: '#8b9ab0', fontSize: '16px', marginBottom: '24px' }}>
              Your payment is being processed. This usually takes a few seconds.
            </p>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '12px 24px',
                background: 'rgba(255, 214, 10, 0.1)',
                border: '1px solid rgba(255, 214, 10, 0.3)',
                borderRadius: '8px',
                color: '#ffd60a',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Check Again
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <div style={{
              width: '80px',
              height: '80px',
              background: 'rgba(239, 68, 68, 0.1)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
              fontSize: '40px',
              border: '2px solid rgba(239, 68, 68, 0.3)'
            }}>
              ✗
            </div>
            <h1 style={{ color: '#ef4444', fontSize: '28px', fontWeight: 700, marginBottom: '12px' }}>
              Something went wrong
            </h1>
            <p style={{ color: '#8b9ab0', fontSize: '16px', marginBottom: '24px' }}>
              We could not verify your payment. Please contact support if you were charged.
            </p>
            <Link
              href="/pricing"
              style={{
                display: 'inline-block',
                padding: '12px 24px',
                background: 'rgba(255, 214, 10, 0.1)',
                border: '1px solid rgba(255, 214, 10, 0.3)',
                borderRadius: '8px',
                color: '#ffd60a',
                fontSize: '14px',
                fontWeight: 600,
                textDecoration: 'none'
              }}
            >
              Back to Pricing
            </Link>
          </>
        )}
      </div>
    </div>
  )
}

export default function PaymentSuccessPage() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #030608 0%, #0a0f18 100%)'
      }}>
        <div style={{
          width: '64px',
          height: '64px',
          border: '3px solid rgba(255, 214, 10, 0.3)',
          borderTopColor: '#ffd60a',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
      </div>
    }>
      <PaymentSuccessContent />
    </Suspense>
  )
}
