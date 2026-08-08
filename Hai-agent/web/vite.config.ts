import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  /** 读取两个后端地址，并在开发环境统一隐藏跨域细节。 */
  const env = loadEnv(mode, process.cwd(), '')
  return { plugins: [vue()], server: { host: '127.0.0.1', port: 5174, proxy: {
    '/api': { target: env.VITE_HAI_BACKEND_URL || 'http://127.0.0.1:8093', changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
    '/ai-api': { target: env.VITE_AI_BACKEND_URL || 'http://127.0.0.1:8090', changeOrigin: true, rewrite: (path) => path.replace(/^\/ai-api/, '') },
  } } }
})