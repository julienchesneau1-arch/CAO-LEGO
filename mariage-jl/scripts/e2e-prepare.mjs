#!/usr/bin/env node
/**
 * Base jetable des parcours Playwright. Lancée avant le serveur, pour qu'il
 * ne se connecte jamais à une base en cours de recréation.
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, readlinkSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = "jl_e2e";
const URL_ADMIN =
  process.env.JL_TEST_DATABASE_URL ?? "postgres://postgres@127.0.0.1:55432/postgres";
const URL_E2E = new URL(`/${BASE}`, URL_ADMIN).href;

const FOYER = {
  label: "Foyer d'essai Playwright",
  jeton: "essai2playwright3foyer4reconnu567",
  code: "TEST42",
  invite: "Camille",
};

const empreinte = (secret) =>
  createHash("sha256").update(secret.trim().toLowerCase(), "utf8").digest();

/**
 * Une exécution interrompue laisse son serveur vivant sur le port des tests,
 * et Playwright refuse alors de démarrer. On libère le port plutôt que de
 * demander à l'humain de chercher le processus.
 */
function libererPort(port) {
  const cible = port.toString(16).toUpperCase().padStart(4, "0");
  const inodes = new Set();
  for (const ligne of readFileSync("/proc/net/tcp", "utf8").split("\n").slice(1)) {
    const champs = ligne.trim().split(/\s+/);
    if (champs.length > 9 && champs[1]?.split(":")[1] === cible && champs[3] === "0A") {
      inodes.add(champs[9]);
    }
  }
  if (inodes.size === 0) return;

  for (const pid of readdirSync("/proc").filter((nom) => /^\d+$/.test(nom))) {
    let descripteurs = [];
    try {
      descripteurs = readdirSync(`/proc/${pid}/fd`);
    } catch {
      continue; // processus disparu ou hors de portée
    }
    for (const fd of descripteurs) {
      try {
        if (inodes.has(readlinkSync(`/proc/${pid}/fd/${fd}`).replace(/^socket:\[(\d+)\]$/, "$1"))) {
          process.kill(Number(pid), "SIGTERM");
          console.log(`Port ${port} libéré (processus ${pid} arrêté).`);
          return;
        }
      } catch {
        /* descripteur volatile */
      }
    }
  }
}

try {
  libererPort(Number(process.env.JL_E2E_PORT ?? 3220));
} catch (erreur) {
  console.log(`Libération du port impossible (${erreur.message}) — on continue.`);
}

const gestion = new pg.Client({ connectionString: URL_ADMIN });
await gestion.connect();
await gestion.query(
  `select pg_terminate_backend(pid) from pg_stat_activity
    where datname = $1 and pid <> pg_backend_pid()`,
  [BASE],
);
await gestion.query(`drop database if exists ${BASE}`);
await gestion.query(`create database ${BASE}`);
await gestion.end();

const client = new pg.Client({ connectionString: URL_E2E });
await client.connect();
for (const fichier of [
  join(RACINE, "supabase", "tests", "00_compat_local.sql"),
  ...readdirSync(join(RACINE, "supabase", "migrations"))
    .filter((f) => f.endsWith(".sql"))
    .sort()
    .map((f) => join(RACINE, "supabase", "migrations", f)),
]) {
  await client.query(readFileSync(fichier, "utf8"));
}
const { rows } = await client.query(
  `insert into public.households (label_public, token_sha256, backup_code_sha256)
   values ($1, $2, $3) returning id`,
  [FOYER.label, empreinte(FOYER.jeton), empreinte(FOYER.code)],
);
await client.query(`insert into public.guests (household_id, first_name) values ($1, $2)`, [
  rows[0].id,
  FOYER.invite,
]);
await client.end();

console.log(`Base « ${BASE} » prête pour les parcours Playwright.`);
