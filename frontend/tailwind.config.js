/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0a',
        surface: '#111111',
        'surface-2': '#1a1a1a',
        border: '#2a2a2a',
        accent: '#f59e0b',
        'accent-dim': '#d97706',
        'text-primary': '#f5f5f5',
        'text-muted': '#6b7280',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}