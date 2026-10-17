import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies the hub (python -m hub.server, port 8780); `npm run build` writes dist/, which the hub serves.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { port: 5178, proxy: { "/api": { target: "http://127.0.0.1:8780", changeOrigin: true } } },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
});
