import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8001',
      '/race': 'http://localhost:8001',
      '/venues': 'http://localhost:8001',
      '/horses': 'http://localhost:8001',
      '/races': 'http://localhost:8001',
      '/tags': 'http://localhost:8001',
      '/ws': { target: 'ws://localhost:8001', ws: true },
    },
  },
})
