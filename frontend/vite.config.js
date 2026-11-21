import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // /api/trips/ in React → http://localhost:8000/api/trips/ (Django)
      '/api': 'http://localhost:8000',
    },
  },
})