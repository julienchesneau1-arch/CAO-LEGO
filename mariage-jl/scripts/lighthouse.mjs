#!/usr/bin/env node
/**
 * Mesure Lighthouse mobile (brief §12 : ≥ 95 dans les quatre catégories).
 * Elle tourne contre l'application compilée, pas en développement : le mode
 * développement mesurerait autre chose que ce que verront les invités.
 *
 * Usage : pnpm lighthouse   (après pnpm build)
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import * as chromeLauncher from "chrome-launcher";
import lighthouse from "lighthouse";

const PORT = Number(process.env["PORT"] ?? 3230);
const BASE = `http://127.0.0.1:${PORT}`;
const URL_BASE_DONNEES =
  process.env["JL_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/jl_dev";
const CHEMINS = ["/", "/programme", "/faq"];
const SEUIL = 95;

/**
 * La catégorie « seo » comporte un audit « la page est bloquée à
 * l'indexation » : l'application est volontairement en `noindex` (brief §11,
 * aucune donnée d'invité indexable). Cet audit ne peut donc pas passer, et
 * c'est le comportement voulu — il est exclu du seuil, et signalé.
 */
const AUDITS_VOULUS = new Set(["is-crawlable"]);

const chemin = process.env["JL_CHROMIUM"] ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
if (existsSync(chemin)) process.env["CHROME_PATH"] = chemin;

const serveur = spawn("node", [".next/standalone/server.js"], {
  env: {
    ...process.env,
    PORT: String(PORT),
    HOSTNAME: "127.0.0.1",
    JL_DATABASE_URL: URL_BASE_DONNEES,
    JL_COOKIE_SECRET: "mesure-lighthouse-0123456789abcdefghij",
  },
  stdio: "ignore",
});

const attendre = async () => {
  for (let essai = 0; essai < 60; essai += 1) {
    try {
      if ((await fetch(`${BASE}/api/health`)).ok) return;
    } catch {
      /* démarrage */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Le serveur ne répond pas.");
};

let echecs = 0;
try {
  await attendre();
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless", "--no-sandbox", "--disable-gpu"],
  });
  mkdirSync(new URL("../captures/", import.meta.url), { recursive: true });

  try {
    for (const route of CHEMINS) {
      const resultat = await lighthouse(
        `${BASE}${route}`,
        { port: chrome.port, output: "json", logLevel: "error" },
        undefined,
      );
      if (resultat === undefined) throw new Error(`Lighthouse n'a rien renvoyé pour ${route}`);

      const { categories, audits } = resultat.lhr;
      console.log(`\n${route}`);
      for (const categorie of Object.values(categories)) {
        const note = Math.round((categorie.score ?? 0) * 100);
        const echoues = categorie.auditRefs
          .map((ref) => audits[ref.id])
          .filter((audit) => audit !== undefined && audit.score !== null && audit.score < 0.9)
          .map((audit) => audit.id);
        const voulus = echoues.filter((id) => AUDITS_VOULUS.has(id));
        const reels = echoues.filter((id) => !AUDITS_VOULUS.has(id));
        const suffisant = note >= SEUIL || (reels.length === 0 && voulus.length > 0);

        console.log(
          `  ${suffisant ? "ok " : "NON"} ${categorie.title.padEnd(16)} ${String(note).padStart(3)}` +
            (reels.length > 0 ? `  → ${reels.slice(0, 4).join(", ")}` : "") +
            (voulus.length > 0 ? `  (volontaire : ${voulus.join(", ")})` : ""),
        );
        if (!suffisant) echecs += 1;
      }
      writeFileSync(
        new URL(`../captures/lighthouse${route === "/" ? "-accueil" : route.replace(/\//g, "-")}.json`, import.meta.url),
        JSON.stringify(resultat.lhr, null, 1),
      );
    }
  } finally {
    await chrome.kill();
  }
} finally {
  serveur.kill("SIGTERM");
}

console.log(
  echecs === 0
    ? `\nToutes les catégories atteignent ${SEUIL} (hors audits volontaires).`
    : `\n${echecs} catégorie(s) sous ${SEUIL}.`,
);
process.exit(echecs === 0 ? 0 : 1);
