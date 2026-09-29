'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { getSupabase } from '@/lib/supabase'
import { AuthGuard } from '@/components/auth/AuthGuard'

function ProfileContent() {
  const { user, signOut } = useAuth()
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })
  const [profile, setProfile] = useState({
    full_name: '',
    avatar_url: ''
  })
  const router = useRouter()
  const supabase = getSupabase()

  useEffect(() => {
    if (user) {
      setProfile({
        full_name: user.user_metadata?.full_name || '',
        avatar_url: user.user_metadata?.avatar_url || ''
      })
    }
  }, [user])

  const handleUpdateProfile = async (e) => {
    e.preventDefault()
    setLoading(true)
    setMessage({ type: '', text: '' })

    try {
      const { error } = await supabase.auth.updateUser({
        data: {
          full_name: profile.full_name
        }
      })

      if (error) throw error
      setMessage({ type: 'success', text: 'Profile updated successfully!' })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setLoading(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await signOut()
      router.push('/login')
    } catch (error) {
      console.error('Error signing out:', error)
    }
  }

  const initials = profile.full_name
    ?.split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || user?.email?.[0]?.toUpperCase() || 'U'

  return (
    <div style={{
      padding: '40px 20px',
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <h1 style={{
        fontSize: '28px',
        fontWeight: 700,
        color: '#e0e6ed',
        marginBottom: '8px'
      }}>
        Account Settings
      </h1>
      <p style={{
        fontSize: '14px',
        color: '#5a6578',
        marginBottom: '40px'
      }}>
        Manage your profile and account preferences
      </p>

      {/* Profile Section */}
      <div style={{
        background: 'rgba(10, 15, 24, 0.8)',
        border: '1px solid rgba(30, 39, 56, 0.8)',
        borderRadius: '12px',
        padding: '32px',
        marginBottom: '24px'
      }}>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: '#e0e6ed',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span>👤</span> Profile Information
        </h2>

        {/* Message */}
        {message.text && (
          <div style={{
            background: message.type === 'success' 
              ? 'rgba(0, 255, 136, 0.1)' 
              : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${message.type === 'success' 
              ? 'rgba(0, 255, 136, 0.3)' 
              : 'rgba(239, 68, 68, 0.3)'}`,
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '20px',
            color: message.type === 'success' ? '#00ff88' : '#ef4444',
            fontSize: '13px'
          }}>
            {message.text}
          </div>
        )}

        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '32px',
          marginBottom: '24px'
        }}>
          {/* Avatar */}
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#0a0f18',
            fontSize: '24px',
            fontWeight: 700,
            flexShrink: 0
          }}>
            {initials}
          </div>

          <form onSubmit={handleUpdateProfile} style={{ flex: 1 }}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#8b9ab0',
                marginBottom: '8px'
              }}>
                Full Name
              </label>
              <input
                type="text"
                value={profile.full_name}
                onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                style={{
                  width: '100%',
                  maxWidth: '320px',
                  padding: '12px 16px',
                  background: 'rgba(30, 39, 56, 0.3)',
                  border: '1px solid rgba(30, 39, 56, 0.8)',
                  borderRadius: '8px',
                  color: '#e0e6ed',
                  fontSize: '14px',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
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
                value={user?.email || ''}
                disabled
                style={{
                  width: '100%',
                  maxWidth: '320px',
                  padding: '12px 16px',
                  background: 'rgba(30, 39, 56, 0.1)',
                  border: '1px solid rgba(30, 39, 56, 0.5)',
                  borderRadius: '8px',
                  color: '#5a6578',
                  fontSize: '14px',
                  cursor: 'not-allowed'
                }}
              />
              <p style={{
                fontSize: '11px',
                color: '#3d4654',
                marginTop: '4px'
              }}>
                Email cannot be changed
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '12px 24px',
                background: loading 
                  ? 'rgba(255, 214, 10, 0.5)' 
                  : 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
                border: 'none',
                borderRadius: '8px',
                color: '#0a0f18',
                fontSize: '14px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </form>
        </div>
      </div>

      {/* Subscription Section */}
      <div style={{
        background: 'rgba(10, 15, 24, 0.8)',
        border: '1px solid rgba(30, 39, 56, 0.8)',
        borderRadius: '12px',
        padding: '32px',
        marginBottom: '24px'
      }}>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: '#e0e6ed',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span>💳</span> Subscription
        </h2>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(30, 39, 56, 0.3)',
          borderRadius: '8px',
          padding: '20px'
        }}>
          <div>
            <div style={{
              display: 'inline-block',
              padding: '4px 12px',
              background: 'rgba(255, 214, 10, 0.2)',
              color: '#ffd60a',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              marginBottom: '8px'
            }}>
              FREE PLAN
            </div>
            <p style={{
              color: '#8b9ab0',
              fontSize: '14px'
            }}>
              Upgrade to Pro for advanced features
            </p>
          </div>
          <a
            href="/pricing"
            style={{
              padding: '10px 20px',
              background: 'rgba(255, 214, 10, 0.1)',
              border: '1px solid rgba(255, 214, 10, 0.3)',
              borderRadius: '8px',
              color: '#ffd60a',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            Upgrade
          </a>
        </div>
      </div>

      {/* Danger Zone */}
      <div style={{
        background: 'rgba(10, 15, 24, 0.8)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderRadius: '12px',
        padding: '32px'
      }}>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: '#ef4444',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span>⚠️</span> Danger Zone
        </h2>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <p style={{
              color: '#e0e6ed',
              fontSize: '14px',
              fontWeight: 500,
              marginBottom: '4px'
            }}>
              Sign out of your account
            </p>
            <p style={{
              color: '#5a6578',
              fontSize: '13px'
            }}>
              You will need to sign in again to access your data
            </p>
          </div>
          <button
            onClick={handleSignOut}
            style={{
              padding: '10px 20px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '8px',
              color: '#ef4444',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  return (
    <AuthGuard>
      <ProfileContent />
    </AuthGuard>
  )
}
