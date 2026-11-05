import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Build -> dist/ (served by FastAPI). Dev proxies /api to the local backend on :8531.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: { '/api': 'http://127.0.0.1:8531' },
  },
  build: { outDir: 'dist', emptyOutDir: true },
});
