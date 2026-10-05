import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Remove console.log in production
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? {
      exclude: ['error', 'warn'],
    } : false,
  },
  
  // Enable React strict mode for better development experience
  reactStrictMode: true,
  
  // Optimize images
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    minimumCacheTTL: 60,
  },
  
  // Enable gzip compression
  compress: true,
  
  // Optimize production builds
  productionBrowserSourceMaps: false, // Disable source maps in production
  
  // Headers for caching and security
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
      {
        // Cache static assets for 1 year
        source: '/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
  
  // Experimental features for performance
  experimental: {
    // Optimize package imports
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons', '@radix-ui/react-dialog', '@radix-ui/react-popover', '@radix-ui/react-select', '@radix-ui/react-tabs', '@radix-ui/react-tooltip', '@radix-ui/react-label', '@radix-ui/react-slot', 'd3', 'framer-motion'],
    // Cap the dev compiler's memory; Turbopack evicts caches above this instead of growing to 4+ GB.
    turbopackMemoryLimit: 1024 * 1024 * 1024,
  },

  turbopack: {
    root: __dirname,
  },
  
  // The old Research V2 and ML V2 UIs were replaced by the /research and /ml workspaces.
  async redirects() {
    return [
      { source: '/labs/research', destination: '/research', permanent: false },
      { source: '/labs/research/:path*', destination: '/research', permanent: false },
      { source: '/labs/research-v2', destination: '/research', permanent: false },
      { source: '/labs/research-v2/:path*', destination: '/research', permanent: false },
      { source: '/labs/ml-v2', destination: '/ml', permanent: false },
      { source: '/labs/ml-v2/:path*', destination: '/ml', permanent: false },
    ];
  },

  // Proxy API requests to FastAPI backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
