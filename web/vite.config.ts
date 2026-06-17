import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// /api 요청은 FastAPI(기본 7000)로 프록시 — API_PORT 환경변수로 변경 가능
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiTarget = `http://localhost:${env.API_PORT || "7000"}`;

  return {
    envDir: "..",
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
      },
    },
    preview: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
      },
    },
    build: {
      outDir: "dist",
    },
  };
});
