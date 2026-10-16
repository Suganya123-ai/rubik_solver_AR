import { type Plugin, defineConfig } from 'vite';
import { resolve } from 'path';

// The Python vision server (see ../README_WEBCAM.md and ../README_PYRAMINX.md). The page
// talks to it through Vite's proxy, so everything is same-origin.
const server = process.env.RUBIK_SERVER ?? 'http://127.0.0.1:8100';

// run_pyra.sh sets PYRA_HOME=1: then the plain address (http://localhost:5175/, what an editor's Ports
// panel opens) shows the Pyraminx app; the cube page stays at /index.html.
const pyraHome = (): Plugin => ({
  name: 'pyra-home',
  configureServer(s) {
    s.middlewares.use((req, _res, next) => {
      if (req.url === '/' || req.url?.startsWith('/?')) req.url = '/pyra.html' + req.url.slice(1);
      next();
    });
  },
});

export default defineConfig({
  plugins: process.env.PYRA_HOME === '1' ? [pyraHome()] : [],
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
