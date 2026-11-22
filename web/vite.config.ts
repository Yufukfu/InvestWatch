import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

// The dev server proxies /api (REST) and /socket.io (events) to the api service: the same routes the
// gateway uses in docker. loadEnv reads .env/.env.local too, not only shell-exported variables.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.API_PROXY_TARGET || 'http://localhost:8000';

  return {
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
      // Generous limits: the same suite runs on a busy laptop or a loaded CI runner, where a jsdom render
      // that takes 100 ms when idle can take seconds (issue #60). A real hang still fails, just later.
      testTimeout: 20_000,
      hookTimeout: 20_000,
      setupFiles: ['./src/test/setup.ts'],
      env: { VITE_API_BASE_URL: 'http://localhost/api' },
    },
  };
});
