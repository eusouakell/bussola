/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type ProxyOptions } from "vite";

// Em dev, o Vite encaminha a API do ADK para o `make agent` (porta 8000).
const ADK = "http://localhost:8000";

// O ADK só aceita Origin igual ao próprio host. Pedidos da página do Vite
// (mesma origem do dev server, cujo Host o Vite já valida) passam a levar a
// origem do ADK; qualquer outra origem segue intacta e o ADK a recusa.
const paraAdk: ProxyOptions = {
  target: ADK,
  changeOrigin: true,
  configure: (proxy) => {
    proxy.on("proxyReq", (saida, entrada) => {
      const origem = entrada.headers.origin;
      if (origem && origem === `http://${entrada.headers.host}`) saida.setHeader("origin", ADK);
    });
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/apps": paraAdk,
      "/run_sse": paraAdk,
    },
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
