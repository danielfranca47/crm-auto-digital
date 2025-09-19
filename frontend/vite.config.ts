import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

export default defineConfig(({ mode }) => ({
  server: {
    host: true,                 // aceita conexões externas (equivale a 0.0.0.0 / ::)
    port: 8080,
    allowedHosts: ["crmapp.danielfranca.pt"],   // <— libera o domínio do túnel
    hmr: {
      host: "crmapp.danielfranca.pt",           // WebSocket do HMR via domínio público
      protocol: "wss",                          // porque a página é https
      clientPort: 443
    },
    strictPort: true
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
