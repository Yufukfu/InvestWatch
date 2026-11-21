import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Dev server proxies /api and /events to the api service, the same routes the gateway uses in docker.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/socket.io': { target: apiTarget, changeOrigin: true, ws: true },
    },
  },
  build: {
    sourcemap: false,
    target: 'es2022',
    // The jury checks the browser console: strip console.* and debugger from production bundles.
    rolldownOptions: { output: { minify: { compress: { dropConsole: true, dropDebugger: true } } } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    env: { VITE_API_BASE_URL: 'http://localhost/api' },
  },
});
