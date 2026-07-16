import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { cloudflare } from "@cloudflare/vite-plugin";
import { sites } from "./build/sites-vite-plugin";

export default defineConfig({
  plugins: [react(), sites(), cloudflare()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": process.env.VITE_API_TARGET || "http://127.0.0.1:8000"
    }
  }
});
