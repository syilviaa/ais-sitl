import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendTarget = process.env.VITE_DEV_BACKEND || 'http://127.0.0.1:5001'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': { target: backendTarget, changeOrigin: true },
      '/socket.io': { target: backendTarget, ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
