#!/usr/bin/env node
/**
 * Base jetable des parcours Playwright. Lancée avant le serveur, pour qu'il
 * ne se connecte jamais à une base en cours de recréation.
 */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { libererPort } from "./liberer-port.mjs";
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

try {
  libererPort(Number(process.env.JL_E2E_PORT ?? 3220));
} catch (erreur) {
  console.log(`Libération du port impossible (${erreur.message}) — on continue.`);
}

// Dossier des souvenirs, vidé à chaque série : un parcours ne doit jamais
// voir les fichiers de la série précédente.
const DOSSIER_MEDIAS = "/tmp/jl-e2e-medias";
rmSync(DOSSIER_MEDIAS, { recursive: true, force: true });
mkdirSync(DOSSIER_MEDIAS, { recursive: true });

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
