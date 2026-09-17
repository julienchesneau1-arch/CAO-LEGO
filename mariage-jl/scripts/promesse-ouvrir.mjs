#!/usr/bin/env node
/**
 * Ouverture des vœux de « La promesse », le 3 juin 2029.
 *
 *   JL_DATABASE_URL=... node scripts/promesse-ouvrir.mjs cle-privee.txt
 *
 * Le script refuse d'ouvrir avant la date de descellement : ce n'est pas une
 * sécurité (qui détient la clé privée peut tout déchiffrer), c'est un garde-
 * fou contre la curiosité et contre l'erreur de manipulation.
 */
import { readFileSync, writeFileSync } from "node:fs";
import pg from "pg";
import { desceller, importerClePrivee } from "../lib/promesse-crypto.ts";

const fichierCle = process.argv[2];
const base = process.env.JL_DATABASE_URL;

if (fichierCle === undefined) {
  console.error("Usage : node scripts/promesse-ouvrir.mjs <fichier-cle-privee>");
  process.exit(2);
}
if (base === undefined) {
  console.error("JL_DATABASE_URL est absent.");
  process.exit(2);
}

const clePrivee = await importerClePrivee(readFileSync(fichierCle, "utf8").replace(/\s+/g, ""));
const client = new pg.Client({ connectionString: base });
await client.connect();

try {
  const { rows } = await client.query(
    `select id, ciphertext, sealed_until, created_at
       from public.promises order by created_at`,
  );
  const aVenir = rows.filter((ligne) => new Date(ligne.sealed_until) > new Date());
  if (aVenir.length > 0) {
    console.error(
      `Refus : ${aVenir.length} vœu(x) ne sont pas encore descellés ` +
        `(le ${new Date(aVenir[0].sealed_until).toISOString().slice(0, 10)}).`,
    );
    process.exit(1);
  }

  const voeux = [];
  let illisibles = 0;
  for (const ligne of rows) {
    try {
      voeux.push(await desceller(JSON.parse(ligne.ciphertext), clePrivee));
    } catch {
      illisibles += 1;
    }
  }

  const sortie = `Les promesses de vos invités — ouvertes le ${new Date()
    .toISOString()
    .slice(0, 10)}\n\n${voeux.map((v, i) => `${i + 1}.\n${v}\n`).join("\n")}`;
  writeFileSync("promesses.txt", sortie);
  console.log(`${voeux.length} vœu(x) écrits dans promesses.txt.`);
  if (illisibles > 0) console.error(`${illisibles} vœu(x) illisibles avec cette clé.`);
} finally {
  await client.end();
}
