#!/usr/bin/env node
/**
 * Base de développement : applique le shim local, les migrations, puis pose
 * trois foyers d'essai. Les jetons sont affichés une seule fois, ici, et ne
 * sortent jamais de la machine.
 *
 * Usage : node scripts/seed-dev.mjs  (après ./scripts/pg-local.sh start)
 */
import { createHash, randomBytes } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import pg from "pg";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const URL_ADMIN = process.env.JL_ADMIN_DATABASE_URL ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = process.env.JL_DEV_DATABASE ?? "jl_dev";

const ALPHABET_JETON = "abcdefghijkmnopqrstuvwxyz23456789";
const ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

const tirer = (alphabet, longueur) => {
  const octets = randomBytes(longueur * 2);
  let sortie = "";
  for (let i = 0; sortie.length < longueur; i += 1) {
    const octet = octets[i % octets.length];
    if (octet < 256 - (256 % alphabet.length)) sortie += alphabet[octet % alphabet.length];
  }
  return sortie;
};
const empreinte = (secret) => createHash("sha256").update(secret.trim().toLowerCase(), "utf8").digest();

const gestion = new pg.Client({ connectionString: URL_ADMIN });
await gestion.connect();
await gestion.query(`drop database if exists ${BASE}`);
await gestion.query(`create database ${BASE}`);
await gestion.end();

const client = new pg.Client({ connectionString: new URL(`/${BASE}`, URL_ADMIN).href });
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

const foyers = [
  { label: "Famille d'essai", invites: ["Camille", "Dominique"], repond: false },
  { label: "Foyer d'essai anglophone", invites: ["Alex"], repond: false, langue: "en" },
  { label: "Foyer d'essai ayant répondu", invites: ["Sacha"], repond: true },
];

console.log("\nFoyers de développement (jetons affichés une seule fois) :\n");
for (const foyer of foyers) {
  const jeton = tirer(ALPHABET_JETON, 32);
  const code = tirer(ALPHABET_CODE, 6);
  const { rows } = await client.query(
    `insert into public.households (label_public, token_sha256, backup_code_sha256, lang_default)
     values ($1, $2, $3, $4) returning id`,
    [foyer.label, empreinte(jeton), empreinte(code), foyer.langue ?? "fr"],
  );
  const id = rows[0].id;
  for (const [index, prenom] of foyer.invites.entries()) {
    await client.query(
      `insert into public.guests (household_id, first_name, sort_order) values ($1, $2, $3)`,
      [id, prenom, index],
    );
  }
  if (foyer.repond) {
    await client.query(`insert into public.rsvp (household_id, status) values ($1, 'yes')`, [id]);
  }
  console.log(`  ${foyer.label}`);
  console.log(`    ouverture : /i/${jeton}`);
  console.log(`    code de secours : ${code}  (nom à saisir : ${foyer.invites[0]})\n`);
}

await client.end();
console.log(`Base « ${BASE} » prête. JL_DATABASE_URL=${new URL(`/${BASE}`, URL_ADMIN).href}\n`);
