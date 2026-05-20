import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@tanstack')) return 'query'
            if (id.includes('lucide-react')) return 'icons'
            if (id.includes('date-fns') || id.includes('clsx')) return 'utils'
            return 'vendor'
          }
        },
      },
    },
  },
})
