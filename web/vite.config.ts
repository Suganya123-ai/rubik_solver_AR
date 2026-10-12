import basicSsl from '@vitejs/plugin-basic-ssl';
import { defineConfig } from 'vite';

// The Python vision server for this branch. The page talks to it through
// Vite's proxy, so everything is same-origin (one address to open on the Beam Pro).
const server = process.env.RUBIK_SERVER ?? 'http://127.0.0.1:8200';
// Over Wi-Fi the page must be https, or the browser refuses the camera; a
// self-signed certificate is made automatically (the browser asks to accept
// it once). RUBIK_HTTP=1 serves plain http for use through `adb reverse`
// (USB), where the Beam Pro opens it as localhost.
const https = process.env.RUBIK_HTTP !== '1';

export default defineConfig({
  base: './',           // the built app is served from /glasses/ by glasses_server.py
  plugins: https ? [basicSsl()] : [],
  server: {
    host: true,          // reachable from the Beam Pro on the same Wi-Fi
    port: 5273,
    strictPort: true,
    proxy: {
      '/ws': { target: server.replace(/^http/, 'ws'), ws: true },
      '/health': server,
      '/api': server,
    },
  },
});
