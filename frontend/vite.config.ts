import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: { target: ["chrome109", "firefox115", "safari16.4"] },
  server: { host: "127.0.0.1", strictPort: true },
  test: { include: ["src/**/*.test.ts"] },
});
