'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { getSupabase } from '@/lib/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const { signIn } = useAuth()
  const router = useRouter()
  const supabase = getSupabase()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await signIn(email, password)
      router.push('/portfolio')
    } catch (err) {
      setError(err.message || 'Failed to sign in')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/portfolio`
        }
      })
      if (error) throw error
    } catch (err) {
      setError(err.message || 'Failed to sign in with Google')
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      background: 'linear-gradient(135deg, #0a0f18 0%, #1a1f2e 50%, #0d1117 100%)'
    }}>
      {/* Left Side - Branding */}
      <div style={{
        flex: 1,
        display: 'none',
        padding: '60px',
        background: 'linear-gradient(135deg, rgba(255, 214, 10, 0.05) 0%, rgba(10, 15, 24, 0.95) 100%)',
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column'
      }} className="hidden lg:flex">
        <div style={{ maxWidth: '400px' }}>
          <h1 style={{
            fontSize: '48px',
            fontWeight: 800,
            color: '#ffd60a',
            fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
            letterSpacing: '0.1em',
            marginBottom: '24px'
          }}>
            QUANT360
          </h1>
          <p style={{
            fontSize: '20px',
            color: '#e0e6ed',
            lineHeight: 1.6,
            marginBottom: '32px'
          }}>
            Institutional-grade analytics for the modern trader.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              '📊 Real-time market data from 50+ exchanges',
              '🔬 Advanced portfolio analytics & risk metrics',
              '⚡ Strategy backtesting & optimization',
              '🎯 AI-powered sentiment analysis'
            ].map((feature, i) => (
              <div key={i} style={{
                fontSize: '14px',
                color: '#8b9ab0',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                {feature}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}>
        <div style={{
          width: '100%',
          maxWidth: '400px'
        }}>
          {/* Mobile Logo */}
          <div style={{ textAlign: 'center', marginBottom: '32px' }} className="lg:hidden">
            <h1 style={{
              fontSize: '28px',
              fontWeight: 700,
              color: '#ffd60a',
              fontFamily: "var(--font-mono, 'IBM Plex Mono', monospace)",
              letterSpacing: '0.1em',
              marginBottom: '8px'
            }}>
              QUANT360
            </h1>
          </div>

          <div style={{
            background: 'rgba(10, 15, 24, 0.95)',
            border: '1px solid rgba(30, 39, 56, 0.8)',
            borderRadius: '16px',
            padding: '40px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)'
          }}>
            <h2 style={{
              fontSize: '24px',
              fontWeight: 700,
              color: '#e0e6ed',
              marginBottom: '8px'
            }}>
              Welcome back
            </h2>
            <p style={{
              fontSize: '14px',
              color: '#5a6578',
              marginBottom: '32px'
            }}>
              Sign in to continue to your dashboard
            </p>

            {/* Error Message */}
            {error && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '20px',
                color: '#ef4444',
                fontSize: '13px'
              }}>
                {error}
              </div>
            )}

            {/* Social Login */}
            <button
              onClick={handleGoogleSignIn}
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'rgba(30, 39, 56, 0.5)',
                border: '1px solid rgba(30, 39, 56, 0.8)',
                borderRadius: '8px',
                color: '#e0e6ed',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                marginBottom: '24px',
                transition: 'all 0.2s'
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </button>

            {/* Divider */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '24px'
            }}>
              <div style={{ flex: 1, height: '1px', background: 'rgba(30, 39, 56, 0.8)' }} />
              <span style={{ fontSize: '12px', color: '#5a6578', textTransform: 'uppercase' }}>
                or continue with email
              </span>
              <div style={{ flex: 1, height: '1px', background: 'rgba(30, 39, 56, 0.8)' }} />
            </div>

            {/* Email Login Form */}
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#8b9ab0',
                  marginBottom: '8px'
                }}>
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: 'rgba(30, 39, 56, 0.3)',
                    border: '1px solid rgba(30, 39, 56, 0.8)',
                    borderRadius: '8px',
                    color: '#e0e6ed',
                    fontSize: '14px',
                    outline: 'none',
                    transition: 'border-color 0.2s'
                  }}
                  placeholder="you@example.com"
                />
              </div>

              <div style={{ marginBottom: '8px' }}>
                <label style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#8b9ab0',
                  marginBottom: '8px'
                }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: 'rgba(30, 39, 56, 0.3)',
                    border: '1px solid rgba(30, 39, 56, 0.8)',
                    borderRadius: '8px',
                    color: '#e0e6ed',
                    fontSize: '14px',
                    outline: 'none',
                    transition: 'border-color 0.2s'
                  }}
                  placeholder="••••••••"
                />
              </div>

              <div style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginBottom: '24px'
              }}>
                <Link 
                  href="/forgot-password"
                  style={{ 
                    color: '#ffd60a', 
                    textDecoration: 'none', 
                    fontSize: '13px',
                    fontWeight: 500
                  }}
                >
                  Forgot password?
                </Link>
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  padding: '14px',
                  background: loading 
                    ? 'rgba(255, 214, 10, 0.5)' 
                    : 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#0a0f18',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            {/* Sign Up Link */}
            <div style={{
              marginTop: '24px',
              textAlign: 'center',
              fontSize: '14px',
              color: '#5a6578'
            }}>
              New to Quant360?{' '}
              <Link 
                href="/signup"
                style={{ color: '#ffd60a', textDecoration: 'none', fontWeight: 600 }}
              >
                Create an account
              </Link>
            </div>
          </div>

          {/* Footer */}
          <div style={{
            marginTop: '24px',
            textAlign: 'center',
            fontSize: '12px',
            color: '#3d4654'
          }}>
            By continuing, you agree to our{' '}
            <Link href="/terms" style={{ color: '#5a6578' }}>Terms</Link>
            {' '}and{' '}
            <Link href="/privacy" style={{ color: '#5a6578' }}>Privacy Policy</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
