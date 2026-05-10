import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/stream': 'http://localhost:9000',
      '/chat'  : 'http://localhost:9000',
      '/upload': 'http://localhost:9000',
      '/run'   : 'http://localhost:9000',
      '/skills': 'http://localhost:9000',
      '/health': 'http://localhost:9000',
      '/a2a'   : 'http://localhost:9000',
    },
  },
})
