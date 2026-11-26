import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiKey = env.SOLARNEXUS_API_KEY?.trim()

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: env.SOLARNEXUS_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          configure(proxy) {
            if (apiKey) {
              proxy.on('proxyReq', (proxyReq) => proxyReq.setHeader('X-API-Key', apiKey))
            }
          },
        },
      },
    },
  }
})
