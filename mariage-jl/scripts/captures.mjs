#!/usr/bin/env node
/**
 * Captures d'écran mobile exigées à chaque livraison (brief §0, méthode 2).
 * Téléphone simulé : 390 × 844, densité 3 — proche d'un iPhone courant.
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { chromium, devices } from "@playwright/test";

const PORT = 3210;
const BASE = `http://127.0.0.1:${PORT}`;
const DOSSIER = new URL("../captures/", import.meta.url);
mkdirSync(DOSSIER, { recursive: true });

const serveur = spawn("node", [".next/standalone/server.js"], {
  env: { ...process.env, PORT: String(PORT), HOSTNAME: "127.0.0.1" },
  cwd: new URL("..", import.meta.url).pathname,
  stdio: "ignore",
});

const attendre = async () => {
  for (let essai = 0; essai < 60; essai += 1) {
    try {
      const r = await fetch(`${BASE}/api/health`);
      if (r.ok) return;
    } catch {
      /* le serveur démarre encore */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Le serveur ne répond pas.");
};

try {
  await attendre();
  // Chromium est préinstallé dans cet environnement : on le désigne
  // explicitement plutôt que de télécharger un binaire.
  const chemin = process.env["JL_CHROMIUM"] ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const navigateur = await chromium.launch(
    existsSync(chemin) ? { executablePath: chemin } : {},
  );
  const contexte = await navigateur.newContext({
    ...devices["iPhone 13"],
    locale: "fr-FR",
    timezoneId: "Europe/Paris",
  });
  const page = await contexte.newPage();

  const capturer = async (nom, url, prefs) => {
    await page.goto(url, { waitUntil: "networkidle" });
    if (prefs) {
      await page.evaluate((p) => {
        localStorage.setItem("jl_confort", JSON.stringify(p));
      }, prefs);
      await page.reload({ waitUntil: "networkidle" });
    }
    await page.waitForTimeout(700);
    await page.screenshot({ path: new URL(`${nom}.png`, DOSSIER).pathname, fullPage: true });
    console.log(`capture : ${nom}.png`);
  };

  await capturer("01-accueil-v0", `${BASE}/`, null);
  await capturer("02-design-normale", `${BASE}/design`, { taille: "normale", papier: "non", mouvement: "normal" });
  await capturer("03-design-tres-grande", `${BASE}/design`, { taille: "tres-grande", papier: "non", mouvement: "normal" });
  await capturer("04-design-papier", `${BASE}/design`, { taille: "normale", papier: "oui", mouvement: "normal" });
  await page.goto(new URL("../secours/index.html", import.meta.url).href, { waitUntil: "load" });
  await page.screenshot({ path: new URL("05-page-de-secours.png", DOSSIER).pathname, fullPage: true });
  console.log("capture : 05-page-de-secours.png");

  await navigateur.close();
} finally {
  serveur.kill("SIGTERM");
}
