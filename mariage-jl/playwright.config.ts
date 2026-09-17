import { defineConfig, devices } from "@playwright/test";
import { URL_E2E } from "./tests/e2e/fixtures";

const PORT = 3220;

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /.*\.spec\.ts/,
  // La base jetable est créée par `scripts/e2e-prepare.mjs`, lancé AVANT
  // Playwright : un globalSetup tournerait après le démarrage du serveur, dont
  // le pool serait alors branché sur une base qui vient d'être recréée.
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    // `--no-sandbox` : ces tests tournent dans un conteneur en root, où le
    // bac à sable de Chromium n'est pas disponible.
    launchOptions: { args: ["--no-sandbox"] },
    locale: "fr-FR",
    timezoneId: "Europe/Paris",
    trace: "off",
  },
  /**
   * Deux gabarits de téléphone, tous deux rendus par Chromium.
   * LIMITE ASSUMÉE : `devices["iPhone 13"]` utiliserait WebKit, qui n'est pas
   * installé dans cet environnement. Le gabarit iPhone vérifie donc la mise
   * en page et les gestes, pas le moteur de Safari. Le brief §12 exige Safari
   * iOS : il doit être vérifié sur un appareil réel avant la validation de V1
   * (voir docs/PLAN.md §10).
   */
  projects: [
    { name: "iPhone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "Android", use: { ...devices["Pixel 7"], browserName: "chromium" } },
  ],
  webServer: {
    command: "node .next/standalone/server.js",
    // Sonde de démarrage sans base : /api/health répond 503 tant que la base
    // jetable n'est pas créée par globalSetup, qui tourne après le serveur.
    url: `http://127.0.0.1:${PORT}/retrouver`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      PORT: String(PORT),
      HOSTNAME: "127.0.0.1",
      JL_DATABASE_URL: URL_E2E,
      JL_COOKIE_SECRET: "secret-de-test-playwright-0123456789abcdef",
      JL_VERSION: "e2e",
    },
  },
});
