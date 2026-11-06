'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { Toaster } from 'react-hot-toast'
import { ThemeProvider } from '@/context/ThemeContext'

export function Providers({ children }) {
  const [queryClient] = useState(() => new QueryClient())
  return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          {children}
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: '#161B22',
                border: '1px solid #30363D',
                color: '#E6EDF3',
                fontFamily: 'var(--font-jetbrains), JetBrains Mono, monospace',
                fontSize: '12px',
              },
            }}
          />
        </QueryClientProvider>
      </ThemeProvider>
  )
}
