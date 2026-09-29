'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

// Currency configuration
const CURRENCIES = {
  USD: { symbol: '$', rate: 1, name: 'USD' },
  INR: { symbol: '₹', rate: 83, name: 'INR' } // Approximate exchange rate
}

const PRICING_DATA = {
  Basic: {
    usd: { monthly: 0, yearly: 0 },
    tagline: 'For curious minds',
    icon: '◈',
    color: '#5a6578',
    features: [
      'Real-time quotes',
      '5 watchlist stocks',
      'Basic charting',
      'Daily market digest',
      'Community access'
    ],
    limitations: [
      'Limited indicators',
      'No backtesting',
      'No API access'
    ]
  },
  Pro: {
    usd: { monthly: 29, yearly: 290 },
    tagline: 'For serious traders',
    icon: '◆',
    color: '#ffd60a',
    popular: true,
    features: [
      'Everything in Basic',
      '50+ technical indicators',
      'Portfolio analytics',
      'Strategy backtesting',
      'Sentiment analysis',
      'Options flow',
      '50 price alerts',
      'Priority support'
    ],
    limitations: []
  },
  Enterprise: {
    usd: { monthly: 99, yearly: 990 },
    tagline: 'For institutions',
    icon: '◇',
    color: '#00d4ff',
    features: [
      'Everything in Pro',
      'Unlimited everything',
      'Full API access',
      'Walk-forward optimization',
      'Multi-asset class',
      'Custom indicators',
      'White-label options',
      'Dedicated manager'
    ],
    limitations: []
  }
}

export default function PricingPage() {
  const [currency, setCurrency] = useState('USD')
  const [billing, setBilling] = useState('yearly')
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  // Track mouse for gradient effect
  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({ x: e.clientX, y: e.clientY })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const getPrice = (tier) => {
    const basePrice = billing === 'yearly' 
      ? PRICING_DATA[tier].usd.yearly / 12 
      : PRICING_DATA[tier].usd.monthly
    
    const converted = Math.round(basePrice * CURRENCIES[currency].rate)
    return converted
  }

  const formatPrice = (amount) => {
    if (amount === 0) return 'Free'
    return `${CURRENCIES[currency].symbol}${amount.toLocaleString()}`
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#030608',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Animated Background */}
      <div style={{
        position: 'fixed',
        inset: 0,
        background: `radial-gradient(circle at ${mousePos.x}px ${mousePos.y}px, rgba(255, 214, 10, 0.03) 0%, transparent 50%)`,
        pointerEvents: 'none',
        transition: 'background 0.3s ease'
      }} />
      
      {/* Grid Pattern */}
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundImage: `
          linear-gradient(rgba(255, 214, 10, 0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255, 214, 10, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
        pointerEvents: 'none'
      }} />

      {/* Floating Orbs */}
      <div style={{
        position: 'fixed',
        top: '20%',
        left: '10%',
        width: '300px',
        height: '300px',
        background: 'radial-gradient(circle, rgba(255, 214, 10, 0.1) 0%, transparent 70%)',
        borderRadius: '50%',
        filter: 'blur(60px)',
        animation: 'float 8s ease-in-out infinite'
      }} />
      <div style={{
        position: 'fixed',
        bottom: '20%',
        right: '10%',
        width: '400px',
        height: '400px',
        background: 'radial-gradient(circle, rgba(0, 212, 255, 0.08) 0%, transparent 70%)',
        borderRadius: '50%',
        filter: 'blur(80px)',
        animation: 'float 10s ease-in-out infinite reverse'
      }} />

      <style jsx>{`
        @keyframes float {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-30px) scale(1.05); }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 10 }}>
        {/* Hero Section */}
        <section style={{
          padding: '100px 20px 60px',
          textAlign: 'center',
          maxWidth: '900px',
          margin: '0 auto'
        }}>
          {/* Eyebrow */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            background: 'rgba(255, 214, 10, 0.1)',
            border: '1px solid rgba(255, 214, 10, 0.2)',
            borderRadius: '100px',
            marginBottom: '24px'
          }}>
            <span style={{
              width: '6px',
              height: '6px',
              background: '#00ff88',
              borderRadius: '50%',
              animation: 'pulse 2s infinite'
            }} />
            <span style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#ffd60a',
              letterSpacing: '0.1em',
              textTransform: 'uppercase'
            }}>
              Special Launch Pricing
            </span>
          </div>

          {/* Main Headline - Creative Typography */}
          <h1 style={{
            fontSize: 'clamp(36px, 7vw, 72px)',
            fontWeight: 800,
            lineHeight: 1.1,
            marginBottom: '24px',
            fontFamily: "'Syne', sans-serif"
          }}>
            <span style={{ color: '#e0e6ed' }}>Trade </span>
            <span style={{
              background: 'linear-gradient(135deg, #ffd60a 0%, #ff6b35 50%, #ffd60a 100%)',
              backgroundSize: '200% auto',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              animation: 'shimmer 3s linear infinite'
            }}>smarter</span>
            <span style={{ color: '#3d4654' }}>,</span>
            <br />
            <span style={{ color: '#5a6578', fontWeight: 400 }}>not </span>
            <span style={{ color: '#3d4654', fontWeight: 400, fontStyle: 'italic' }}>harder</span>
          </h1>

          <p style={{
            fontSize: '18px',
            color: '#5a6578',
            maxWidth: '500px',
            margin: '0 auto 48px',
            lineHeight: 1.7
          }}>
            Join <span style={{ color: '#ffd60a', fontWeight: 600 }}>50,000+</span> traders using 
            institutional-grade analytics. Start free, upgrade anytime.
          </p>

          {/* Controls */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '24px',
            flexWrap: 'wrap',
            marginBottom: '60px'
          }}>
            {/* Currency Toggle */}
            <div style={{
              display: 'flex',
              background: 'rgba(10, 15, 24, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(30, 39, 56, 0.5)',
              borderRadius: '12px',
              padding: '4px'
            }}>
              {Object.keys(CURRENCIES).map((curr) => (
                <button
                  key={curr}
                  onClick={() => setCurrency(curr)}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    background: currency === curr 
                      ? 'linear-gradient(135deg, rgba(255, 214, 10, 0.2) 0%, rgba(255, 214, 10, 0.1) 100%)'
                      : 'transparent',
                    color: currency === curr ? '#ffd60a' : '#5a6578',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <span style={{ fontSize: '16px' }}>{CURRENCIES[curr].symbol}</span>
                  {curr}
                </button>
              ))}
            </div>

            {/* Billing Toggle */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'rgba(10, 15, 24, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(30, 39, 56, 0.5)',
              borderRadius: '12px',
              padding: '4px'
            }}>
              <button
                onClick={() => setBilling('monthly')}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: billing === 'monthly' 
                    ? 'rgba(30, 39, 56, 0.5)' 
                    : 'transparent',
                  color: billing === 'monthly' ? '#e0e6ed' : '#5a6578',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                Monthly
              </button>
              <button
                onClick={() => setBilling('yearly')}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: billing === 'yearly' 
                    ? 'rgba(30, 39, 56, 0.5)' 
                    : 'transparent',
                  color: billing === 'yearly' ? '#e0e6ed' : '#5a6578',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                Yearly
                <span style={{
                  padding: '2px 8px',
                  background: 'rgba(0, 255, 136, 0.15)',
                  color: '#00ff88',
                  borderRadius: '4px',
                  fontSize: '10px',
                  fontWeight: 700
                }}>
                  -17%
                </span>
              </button>
            </div>
          </div>
        </section>

        {/* Pricing Cards */}
        <section style={{
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '0 20px 100px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
          alignItems: 'stretch'
        }}>
          {Object.entries(PRICING_DATA).map(([tier, data]) => (
            <div
              key={tier}
              style={{
                position: 'relative',
                background: data.popular 
                  ? 'linear-gradient(135deg, rgba(255, 214, 10, 0.08) 0%, rgba(10, 15, 24, 0.95) 50%, rgba(0, 212, 255, 0.05) 100%)'
                  : 'rgba(10, 15, 24, 0.6)',
                backdropFilter: 'blur(20px)',
                border: data.popular 
                  ? '2px solid rgba(255, 214, 10, 0.4)'
                  : '1px solid rgba(30, 39, 56, 0.5)',
                borderRadius: '24px',
                padding: '40px 32px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                transition: 'transform 0.3s, border-color 0.3s',
                transform: data.popular ? 'scale(1.02)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (!data.popular) {
                  e.currentTarget.style.borderColor = 'rgba(255, 214, 10, 0.3)'
                  e.currentTarget.style.transform = 'translateY(-4px)'
                }
              }}
              onMouseLeave={(e) => {
                if (!data.popular) {
                  e.currentTarget.style.borderColor = 'rgba(30, 39, 56, 0.5)'
                  e.currentTarget.style.transform = 'none'
                }
              }}
            >
              {/* Popular Badge */}
              {data.popular && (
                <div style={{
                  position: 'absolute',
                  top: '20px',
                  right: '20px',
                  padding: '6px 12px',
                  background: 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
                  color: '#0a0f18',
                  borderRadius: '6px',
                  fontSize: '10px',
                  fontWeight: 800,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase'
                }}>
                  Most Popular
                </div>
              )}

              {/* Icon */}
              <div style={{
                width: '56px',
                height: '56px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: `${data.color}15`,
                borderRadius: '16px',
                marginBottom: '24px',
                fontSize: '24px',
                color: data.color
              }}>
                {data.icon}
              </div>

              {/* Tier Name */}
              <h3 style={{
                fontSize: '28px',
                fontWeight: 700,
                color: '#e0e6ed',
                marginBottom: '4px',
                fontFamily: "'Syne', sans-serif"
              }}>
                {tier}
              </h3>

              <p style={{
                fontSize: '14px',
                color: '#5a6578',
                marginBottom: '24px'
              }}>
                {data.tagline}
              </p>

              {/* Price */}
              <div style={{ marginBottom: '32px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: '4px'
                }}>
                  <span style={{
                    fontSize: '48px',
                    fontWeight: 800,
                    color: data.color,
                    fontFamily: "'IBM Plex Mono', monospace"
                  }}>
                    {formatPrice(getPrice(tier))}
                  </span>
                  {getPrice(tier) > 0 && (
                    <span style={{
                      fontSize: '14px',
                      color: '#5a6578'
                    }}>
                      /mo
                    </span>
                  )}
                </div>
                {billing === 'yearly' && getPrice(tier) > 0 && (
                  <p style={{
                    fontSize: '12px',
                    color: '#3d4654',
                    marginTop: '4px'
                  }}>
                    Billed {formatPrice(getPrice(tier) * 12)} yearly
                  </p>
                )}
              </div>

              {/* CTA */}
              <Link
                href={tier === 'Enterprise' ? '/contact' : '/signup'}
                style={{
                  display: 'block',
                  textAlign: 'center',
                  padding: '16px 24px',
                  background: data.popular 
                    ? 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)'
                    : `${data.color}15`,
                  border: data.popular ? 'none' : `1px solid ${data.color}40`,
                  borderRadius: '12px',
                  color: data.popular ? '#0a0f18' : data.color,
                  fontSize: '14px',
                  fontWeight: 700,
                  textDecoration: 'none',
                  marginBottom: '32px',
                  transition: 'all 0.2s'
                }}
              >
                {tier === 'Basic' ? 'Get Started Free' : tier === 'Enterprise' ? 'Contact Sales' : 'Start 14-Day Trial'}
              </Link>

              {/* Features */}
              <div style={{ flex: 1 }}>
                <p style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#3d4654',
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  marginBottom: '16px'
                }}>
                  What&apos;s included
                </p>
                <ul style={{
                  listStyle: 'none',
                  padding: 0,
                  margin: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  {data.features.map((feature, i) => (
                    <li
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        fontSize: '14px',
                        color: '#8b9ab0'
                      }}
                    >
                      <span style={{
                        color: '#00ff88',
                        fontSize: '12px'
                      }}>✓</span>
                      {feature}
                    </li>
                  ))}
                  {data.limitations.map((limit, i) => (
                    <li
                      key={`limit-${i}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        fontSize: '14px',
                        color: '#3d4654'
                      }}
                    >
                      <span style={{ fontSize: '12px' }}>✗</span>
                      {limit}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </section>

        {/* Trust Section */}
        <section style={{
          padding: '80px 20px',
          background: 'rgba(10, 15, 24, 0.5)',
          borderTop: '1px solid rgba(30, 39, 56, 0.3)',
          borderBottom: '1px solid rgba(30, 39, 56, 0.3)'
        }}>
          <div style={{
            maxWidth: '1000px',
            margin: '0 auto',
            textAlign: 'center'
          }}>
            <p style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#3d4654',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              marginBottom: '32px'
            }}>
              Trusted by traders worldwide
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '40px',
              alignItems: 'center',
              justifyItems: 'center'
            }}>
              {['₹2.4Cr+', '$50M+', '52', '99.9%', '24/7'].map((stat, i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <div style={{
                    fontSize: '28px',
                    fontWeight: 800,
                    color: '#ffd60a',
                    fontFamily: "'IBM Plex Mono', monospace",
                    marginBottom: '4px'
                  }}>
                    {stat}
                  </div>
                  <div style={{
                    fontSize: '11px',
                    color: '#5a6578',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em'
                  }}>
                    {['Assets (India)', 'Assets (Global)', 'Exchanges', 'Uptime', 'Support'][i]}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ Section */}
        <section style={{
          maxWidth: '700px',
          margin: '0 auto',
          padding: '80px 20px'
        }}>
          <h2 style={{
            fontSize: '32px',
            fontWeight: 700,
            textAlign: 'center',
            marginBottom: '48px',
            fontFamily: "'Syne', sans-serif"
          }}>
            <span style={{ color: '#5a6578' }}>Frequently asked </span>
            <span style={{ color: '#ffd60a' }}>questions</span>
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              {
                q: 'Can I pay in Indian Rupees (₹)?',
                a: 'Yes! We accept payments in both USD and INR. For Indian customers, we use Razorpay for seamless UPI, card, and net banking payments. International customers can pay via Stripe.'
              },
              {
                q: 'What happens after the 14-day trial?',
                a: 'Your trial converts to a paid subscription. No payment is required upfront. Cancel anytime during the trial period with no charges.'
              },
              {
                q: 'Can I switch between plans?',
                a: 'Absolutely. Upgrade instantly, downgrade at the end of your billing cycle. Prorated credits apply for upgrades.'
              },
              {
                q: 'Is my data secure?',
                a: 'We use bank-grade 256-bit SSL encryption. Your data is never shared with third parties. We are SOC 2 Type II compliant.'
              },
              {
                q: 'Do you offer refunds?',
                a: '30-day money-back guarantee on annual plans. No questions asked. Monthly plans can be cancelled anytime.'
              }
            ].map((item, i) => (
              <details
                key={i}
                style={{
                  background: 'rgba(10, 15, 24, 0.6)',
                  border: '1px solid rgba(30, 39, 56, 0.5)',
                  borderRadius: '12px',
                  overflow: 'hidden'
                }}
              >
                <summary style={{
                  padding: '20px 24px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#e0e6ed',
                  listStyle: 'none',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  {item.q}
                  <span style={{ color: '#ffd60a' }}>+</span>
                </summary>
                <div style={{
                  padding: '0 24px 20px',
                  fontSize: '14px',
                  color: '#8b9ab0',
                  lineHeight: 1.7
                }}>
                  {item.a}
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* Final CTA */}
        <section style={{
          padding: '80px 20px',
          textAlign: 'center',
          background: 'linear-gradient(135deg, rgba(255, 214, 10, 0.05) 0%, rgba(10, 15, 24, 0) 50%)'
        }}>
          <h2 style={{
            fontSize: 'clamp(28px, 5vw, 42px)',
            fontWeight: 700,
            marginBottom: '16px',
            fontFamily: "'Syne', sans-serif"
          }}>
            <span style={{ color: '#e0e6ed' }}>Ready to level up?</span>
          </h2>
          <p style={{
            fontSize: '16px',
            color: '#5a6578',
            marginBottom: '32px'
          }}>
            14-day free trial • No credit card required
          </p>
          <Link
            href="/signup"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '12px',
              padding: '18px 40px',
              background: 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
              color: '#0a0f18',
              borderRadius: '12px',
              fontSize: '16px',
              fontWeight: 700,
              textDecoration: 'none',
              transition: 'transform 0.2s, box-shadow 0.2s'
            }}
          >
            Start Free Trial
            <span>→</span>
          </Link>
        </section>

        {/* Footer */}
        <footer style={{
          padding: '40px 20px',
          borderTop: '1px solid rgba(30, 39, 56, 0.3)',
          textAlign: 'center'
        }}>
          <p style={{
            fontSize: '12px',
            color: '#3d4654'
          }}>
            © {new Date().getFullYear()} Quant360. All rights reserved.
          </p>
        </footer>
      </div>
    </div>
  )
}
