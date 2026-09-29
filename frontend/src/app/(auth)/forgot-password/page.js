'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  
  const { resetPassword } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await resetPassword(email)
      setSuccess(true)
    } catch (err) {
      setError(err.message || 'Failed to send reset email')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #0a0f18 0%, #1a1f2e 50%, #0d1117 100%)',
        padding: '20px'
      }}>
        <div style={{
          width: '100%',
          maxWidth: '420px',
          background: 'rgba(10, 15, 24, 0.95)',
          border: '1px solid rgba(0, 255, 136, 0.3)',
          borderRadius: '12px',
          padding: '40px',
          textAlign: 'center'
        }}>
          <div style={{
            width: '60px',
            height: '60px',
            background: 'rgba(0, 255, 136, 0.1)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            fontSize: '28px'
          }}>
            ✉️
          </div>
          <h2 style={{ color: '#00ff88', marginBottom: '12px', fontSize: '20px' }}>
            Check your email!
          </h2>
          <p style={{ color: '#8b9ab0', fontSize: '14px', marginBottom: '24px' }}>
            We have sent a password reset link to <strong style={{color: '#e0e6ed'}}>{email}</strong>
          </p>
          <Link 
            href="/login"
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              background: 'rgba(255, 214, 10, 0.1)',
              border: '1px solid rgba(255, 214, 10, 0.3)',
              borderRadius: '8px',
              color: '#ffd60a',
              textDecoration: 'none',
              fontSize: '14px',
              fontWeight: 600
            }}
          >
            Back to Login
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0a0f18 0%, #1a1f2e 50%, #0d1117 100%)',
      padding: '20px'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        background: 'rgba(10, 15, 24, 0.95)',
        border: '1px solid rgba(255, 214, 10, 0.2)',
        borderRadius: '12px',
        padding: '40px',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(255, 214, 10, 0.05)'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 700,
            color: '#ffd60a',
            marginBottom: '8px'
          }}>
            Reset Password
          </h1>
          <p style={{
            fontSize: '14px',
            color: '#5a6578'
          }}>
            Enter your email to receive a reset link
          </p>
        </div>

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

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '24px' }}>
            <label style={{
              display: 'block',
              fontSize: '12px',
              fontWeight: 600,
              color: '#8b9ab0',
              marginBottom: '8px',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
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
                background: 'rgba(30, 39, 56, 0.5)',
                border: '1px solid rgba(30, 39, 56, 0.8)',
                borderRadius: '8px',
                color: '#e0e6ed',
                fontSize: '14px',
                outline: 'none'
              }}
              placeholder="you@example.com"
            />
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
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}
          >
            {loading ? 'Sending...' : 'Send Reset Link'}
          </button>
        </form>

        {/* Back Link */}
        <div style={{
          marginTop: '24px',
          textAlign: 'center',
          fontSize: '13px',
          color: '#5a6578'
        }}>
          Remember your password?{' '}
          <Link 
            href="/login"
            style={{ color: '#ffd60a', textDecoration: 'none', fontWeight: 600 }}
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
