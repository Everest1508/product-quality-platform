import path from 'path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Two ways to build the same app:
//  - default: app.js, app.css and page-<hash>.js in dist/, served by Django at /ui/ (what Docker builds).
//  - `--mode hosted` (npm run build:hosted): a normal site in dist-hosted/ (index.html + hashed assets) for a static host such
//    as Vercel. It calls the back end at VITE_API_ORIGIN.
export default defineConfig(({ mode }) => {
  const hosted = mode === 'hosted';
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
    // Django serves the app from /ui/, so a page's own file is found next to app.js instead of at the site root.
    base: hosted ? '/' : '/ui/',
    build: hosted
      ? { outDir: 'dist-hosted', emptyOutDir: true }
      : {
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
  };
});
