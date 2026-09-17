import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
      // `server-only` refuse d'être importé hors d'un composant serveur : c'est
      // exactement son rôle, et Next le remplace par un module vide via la
      // condition d'export « react-server ». Les tests font de même, sinon les
      // bibliothèques serveur seraient intestables.
      "server-only": fileURLToPath(new URL("node_modules/server-only/empty.js", import.meta.url)),
    },
  },
});
