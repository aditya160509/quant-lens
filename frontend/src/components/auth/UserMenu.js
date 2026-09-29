'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'

/**
 * User Menu Component for Navigation
 * Shows user avatar and dropdown with profile/logout options
 */
export function UserMenu() {
  const [isOpen, setIsOpen] = useState(false)
  const { user, signOut, loading } = useAuth()
  const router = useRouter()
  const menuRef = useRef(null)

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSignOut = async () => {
    try {
      await signOut()
      router.push('/login')
    } catch (error) {
      console.error('Sign out error:', error)
    }
  }

  if (loading) {
    return (
      <div style={{
        width: '36px',
        height: '36px',
        borderRadius: '50%',
        background: 'rgba(30, 39, 56, 0.5)',
        animation: 'pulse 2s infinite'
      }} />
    )
  }

  if (!user) {
    return (
      <button
        onClick={() => router.push('/login')}
        style={{
          padding: '8px 16px',
          background: 'rgba(255, 214, 10, 0.1)',
          border: '1px solid rgba(255, 214, 10, 0.3)',
          borderRadius: '6px',
          color: '#ffd60a',
          fontSize: '13px',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'all 0.2s'
        }}
      >
        Sign In
      </button>
    )
  }

  const initials = user.user_metadata?.full_name
    ?.split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || user.email?.[0]?.toUpperCase() || 'U'

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      {/* Avatar Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #ffd60a 0%, #f0c000 100%)',
          border: 'none',
          color: '#0a0f18',
          fontSize: '13px',
          fontWeight: 700,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'transform 0.2s, box-shadow 0.2s',
          boxShadow: isOpen ? '0 0 0 3px rgba(255, 214, 10, 0.3)' : 'none'
        }}
      >
        {initials}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: '220px',
          background: 'rgba(10, 15, 24, 0.98)',
          border: '1px solid rgba(30, 39, 56, 0.8)',
          borderRadius: '8px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5)',
          zIndex: 1000,
          overflow: 'hidden'
        }}>
          {/* User Info */}
          <div style={{
            padding: '16px',
            borderBottom: '1px solid rgba(30, 39, 56, 0.8)'
          }}>
            <div style={{
              fontSize: '14px',
              fontWeight: 600,
              color: '#e0e6ed',
              marginBottom: '4px'
            }}>
              {user.user_metadata?.full_name || 'User'}
            </div>
            <div style={{
              fontSize: '12px',
              color: '#5a6578',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {user.email}
            </div>
          </div>

          {/* Menu Items */}
          <div style={{ padding: '8px' }}>
            <MenuItem 
              icon="👤" 
              label="Profile" 
              onClick={() => { setIsOpen(false); router.push('/profile') }} 
            />
            <MenuItem 
              icon="⚙️" 
              label="Settings" 
              onClick={() => { setIsOpen(false); router.push('/settings') }} 
            />
            <MenuItem 
              icon="📊" 
              label="My Portfolios" 
              onClick={() => { setIsOpen(false); router.push('/portfolio') }} 
            />
          </div>

          {/* Sign Out */}
          <div style={{
            padding: '8px',
            borderTop: '1px solid rgba(30, 39, 56, 0.8)'
          }}>
            <MenuItem 
              icon="🚪" 
              label="Sign Out" 
              onClick={handleSignOut}
              danger
            />
          </div>
        </div>
      )}
    </div>
  )
}

function MenuItem({ icon, label, onClick, danger = false }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        padding: '10px 12px',
        background: 'transparent',
        border: 'none',
        borderRadius: '6px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        cursor: 'pointer',
        color: danger ? '#ef4444' : '#e0e6ed',
        fontSize: '13px',
        transition: 'background 0.15s',
        textAlign: 'left'
      }}
      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(30, 39, 56, 0.5)'}
      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  )
}

export default UserMenu
