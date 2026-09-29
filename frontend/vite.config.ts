import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Em desenvolvimento o Vite responde tudo com o index.html (fallback de SPA), então /scalar
 * abriria o aplicativo. Aqui o endereço é reescrito para o arquivo da página, como o nginx faz em
 * produção — assim o endereço é o mesmo nos dois lugares.
 */
function referenceCleanUrl(): Plugin {
  return {
    name: "scalar-clean-url",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        if (req.url === "/scalar") req.url = "/scalar.html";
        next();
      });
    },
  };
}

// Em desenvolvimento, /api é repassado para o back-end; em produção quem faz isso é o nginx.
export default defineConfig({
  plugins: [react(), referenceCleanUrl()],
  build: {
    // A referência da API (Scalar) gera um pacote grande, mas ele fica só na página dela.
    chunkSizeWarningLimit: 4000,
    rollupOptions: { input: { main: "index.html", reference: "scalar.html" } },
  },
  server: {
    port: 5173,
    proxy: { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" },
  },
});
