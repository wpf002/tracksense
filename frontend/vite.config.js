import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND = 'http://localhost:8001'

// Some prefixes are BOTH a frontend page route (e.g. /training, /horses) and an
// API prefix (e.g. /training/roster). For those, proxy XHR/fetch calls to the
// backend but let Vite serve the SPA on a full-page browser navigation so a
// refresh or deep-link doesn't 404. Browser navigations send `Accept: text/html`;
// axios/fetch API calls do not.
const apiOnly = (req) =>
  req.headers.accept && req.headers.accept.includes('text/html')
    ? '/index.html'
    : undefined

const spa = { target: BACKEND, bypass: apiOnly }

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1000,
  },
  server: {
    proxy: {
      // Pure API prefixes (never a page route)
      '/auth': BACKEND,
      '/admin': BACKEND,
      '/webhooks': BACKEND,
      '/health': BACKEND,
      '/race': BACKEND,
      '/workout': BACKEND,
      '/tags': BACKEND,
      '/hisa': BACKEND,
      '/stewards': BACKEND,
      // Prefixes that are also SPA page routes — serve the app on HTML navigation
      '/venues': spa,
      '/horses': spa,
      '/races': spa,
      '/training': spa,
      '/ws': { target: 'ws://localhost:8001', ws: true },
    },
  },
})
