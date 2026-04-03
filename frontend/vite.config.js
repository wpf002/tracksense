import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/race': 'http://localhost:8000',
      '/venues': 'http://localhost:8000',
      '/horses': 'http://localhost:8000',
      '/races': 'http://localhost:8000',
      '/tags': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
