import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
        '/patients': {
          target: 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        }
      }
    },
    build: {
      // Output directory for production build
      outDir: 'dist',
      // Generate source maps for production (set to false for smaller bundle)
      sourcemap: false,
      // Use default esbuild minifier to avoid optional terser dependency
      minify: true,
    },
    // Define environment variables for the app
    define: {
      'import.meta.env.VITE_AUTH_API_URL': JSON.stringify(env.VITE_AUTH_API_URL || '/api'),
      'import.meta.env.VITE_PATIENT_API_URL': JSON.stringify(env.VITE_PATIENT_API_URL || '/patients'),
    }
  }
})
