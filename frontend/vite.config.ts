// 作用：配置 Vite、React 插件、测试环境和 API 代理。
// Docker 环境下 VITE_API_TARGET=http://backend:8000，本地开发默认 localhost:8000
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts"
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      }
    }
  }
});
