import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    global: 'globalThis',  // amazon-cognito-identity-js requires this in browser
  },
  server: {
    port: 5173,
    historyApiFallback: true,
    proxy: {
      '/chat':    'http://localhost:8000',
      '/thread':  'http://localhost:8000',
      '/health':  'http://localhost:8000',
      '/history': 'http://localhost:8000',
    },
  },
})
