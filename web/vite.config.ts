import { defineConfig } from 'vite';

// The Python vision server for this branch (see ../README_WEBCAM.md). The page
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
});
