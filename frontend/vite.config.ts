import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

export default defineConfig(({ mode }) => ({
  server: {
    host: true,          // aceita conexões externas
    port: 8080,
    // Se não for mais usar túnel, deixe a linha abaixo comentada ou remova:
    // allowedHosts: ["crmapp.danielfranca.pt"],
    hmr: { host: "localhost", protocol: "ws", clientPort: 8080 },
    strictPort: true,
  },
  plugins: [
    react(),
    mode === "development" && componentTagger(),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
