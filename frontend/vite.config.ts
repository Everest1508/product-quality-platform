import path from 'path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  // The app is served from /ui/, so a page's own file is found next to app.js instead of at the site root.
  base: '/ui/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: 'src/main.tsx',
      output: { entryFileNames: 'app.js', chunkFileNames: 'page-[hash].js', assetFileNames: 'app[extname]' },
    },
  },
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'] },
});
