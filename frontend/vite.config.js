import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import process from "node:process";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: ["frontend"],
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
  define: {
    "import.meta.env.VITE_API_BASE_URL": JSON.stringify(""),
  },
});
