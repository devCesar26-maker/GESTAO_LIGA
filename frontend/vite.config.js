import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to Vite only: /api and /django-admin are
// proxied to Django, which keeps the session cookie same-origin (no CORS).
const DJANGO_URL = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: DJANGO_URL,
        changeOrigin: false,
      },
      "/django-admin": {
        target: DJANGO_URL,
        changeOrigin: false,
      },
      "/static": {
        target: DJANGO_URL,
        changeOrigin: false,
      },
    },
  },
  preview: {
    port: 4173,
    host: true,
  },
});
