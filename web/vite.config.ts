import { defineConfig } from 'vite';
import { resolve } from 'path';

// The Python vision server (see ../README_WEBCAM.md and ../README_PYRAMINX.md). The page
// talks to it through Vite's proxy, so everything is same-origin.
const server = process.env.RUBIK_SERVER ?? 'http://127.0.0.1:8100';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/ws': { target: server.replace(/^http/, 'ws'), ws: true },
      '/health': server,
      '/api': server,
    },
  },
  build: {
    rollupOptions: { input: { main: resolve(__dirname, 'index.html'), pyra: resolve(__dirname, 'pyra.html') } },
  },
});
