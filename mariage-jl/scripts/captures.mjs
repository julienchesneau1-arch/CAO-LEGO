#!/usr/bin/env node
/**
 * Captures d'écran mobile exigées à chaque livraison (brief §0, méthode 2).
 * Téléphone simulé : 390 × 844. Le script pose son propre foyer de
 * démonstration dans la base de développement, prend les captures, puis le
 * supprime : aucune donnée réelle, aucun reste.
 *
 * Prérequis : ./scripts/pg-local.sh start && pnpm db:seed && pnpm build
 */
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdirSync } from "node:fs";
import { chromium, devices } from "@playwright/test";
import pg from "pg";

const PORT = Number(process.env["PORT"] ?? 3210);
const BASE = `http://127.0.0.1:${PORT}`;
const URL_BASE_DONNEES =
  process.env["JL_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/jl_dev";
const DOSSIER = new URL("../captures/", import.meta.url);
mkdirSync(DOSSIER, { recursive: true });

const ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789";
const jeton = Array.from(randomBytes(32), (o) => ALPHABET[o % ALPHABET.length]).join("");
const empreinte = (s) => createHash("sha256").update(s.trim().toLowerCase(), "utf8").digest();

const base = new pg.Client({ connectionString: URL_BASE_DONNEES });
await base.connect();
const { rows } = await base.query(
  `insert into public.households (label_public, token_sha256, backup_code_sha256)
   values ('Foyer de démonstration', $1, $2) returning id`,
  [empreinte(jeton), empreinte("DEMO01")],
);
const foyerId = rows[0].id;

const serveur = spawn("node", [".next/standalone/server.js"], {
  env: {
    ...process.env,
    PORT: String(PORT),
    HOSTNAME: "127.0.0.1",
    JL_DATABASE_URL: URL_BASE_DONNEES,
    // Le serveur compilé tourne en NODE_ENV=production : le secret de cookie
    // est alors obligatoire (c'est voulu). On en tire un, jetable.
    JL_COOKIE_SECRET: process.env["JL_COOKIE_SECRET"] ?? randomBytes(32).toString("base64url"),
  },
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
  throw new Error("Le serveur ne répond pas ou la base est injoignable.");
};

try {
  await attendre();
  const chemin = process.env["JL_CHROMIUM"] ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const navigateur = await chromium.launch(existsSync(chemin) ? { executablePath: chemin } : {});
  const contexte = await navigateur.newContext({
    ...devices["iPhone 13"],
    deviceScaleFactor: 1,
    locale: "fr-FR",
    timezoneId: "Europe/Paris",
  });
  const page = await contexte.newPage();
  /**
   * `attente` sert à photographier une animation en cours ; `pageEntiere` est
   * faux pour les écrans en surcouche, qui ne couvrent que la fenêtre.
   */
  const prendre = async (nom, { attente = 1100, pageEntiere = true } = {}) => {
    await page.waitForTimeout(attente);
    await page.screenshot({
      path: new URL(`${nom}.jpg`, DOSSIER).pathname,
      type: "jpeg",
      quality: 75,
      fullPage: pageEntiere,
    });
    console.log(`capture : ${nom}.jpg`);
  };

  // Ouverture par QR : premier lancement en trois écrans.
  await page.goto(`${BASE}/i/${jeton}`, { waitUntil: "networkidle" });
  await prendre("01-ouverture-signature", { attente: 550, pageEntiere: false });
  await page.getByRole("button", { name: "Continuer" }).click();
  await prendre("02-confort-de-lecture", { pageEntiere: false });
  await page.getByRole("button", { name: "Continuer" }).click();
  await prendre("03-bienvenue", { pageEntiere: false });
  await page.getByRole("button", { name: "Tout est ici." }).click();
  await prendre("04-accueil-foyer-reconnu");

  // Confort de lecture « très grande » sur l'accueil.
  await page.evaluate(() =>
    localStorage.setItem(
      "jl_confort",
      JSON.stringify({ taille: "tres-grande", papier: "non", mouvement: "normal" }),
    ),
  );
  await page.reload({ waitUntil: "networkidle" });
  await prendre("05-accueil-tres-grande");

  await page.evaluate(() => localStorage.removeItem("jl_confort"));
  await page.goto(`${BASE}/retrouver`, { waitUntil: "networkidle" });
  await prendre("06-retrouver-mon-invitation");

  await page.goto(`${BASE}/partager`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Créer un lien" }).click();
  await page.waitForLoadState("networkidle");
  await prendre("07-partager-l-acces");

  await page.goto(`${BASE}/design`, { waitUntil: "networkidle" });
  await prendre("08-direction-artistique");

  await page.goto(new URL("../secours/index.html", import.meta.url).href, { waitUntil: "load" });
  await prendre("09-page-de-secours");

  await navigateur.close();
} finally {
  serveur.kill("SIGTERM");
  await base.query("delete from public.households where id = $1", [foyerId]);
  await base.end();
}
