import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    },
    // HMR 설정 개선
    hmr: {
      overlay: true,
    },
    // 파일 감시 설정
    watch: {
      // 불필요한 파일 감시 제외
      ignored: [
        '**/node_modules/**',
        '**/dist/**',
        '**/.git/**',
        '**/backend/**',
        '**/data/**',
        '**/logs/**',
        '**/__pycache__/**',
        '**/*.pyc',
      ],
      // 성능 개선을 위한 설정
      usePolling: false,
    }
  },
  // 빌드 최적화
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'markdown-vendor': ['react-markdown', 'remark-gfm'],
        }
      }
    }
  }
})