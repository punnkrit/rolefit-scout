import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist-admin",
    rollupOptions: {
      input: "admin.html"
    }
  },
  server: {
    port: 5174,
    host: "127.0.0.1",
    strictPort: false,
    proxy: {
      "/api": process.env.VITE_ADMIN_API_TARGET || "http://127.0.0.1:8020"
    }
  }
});
