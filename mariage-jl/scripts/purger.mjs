#!/usr/bin/env node
/**
 * Purges de rétention (brief §11).
 *
 * Deux moitiés, dans cet ordre :
 * 1. `jl.executer_purges()` supprime les lignes arrivées à échéance. Sur
 *    Supabase, pg_cron l'appelle chaque nuit ; ici, on l'appelle à la main.
 * 2. Les fichiers dont la ligne a disparu sont supprimés du disque — ce que
 *    SQL ne peut pas faire.
 * 3. Les lignes dont le fichier a disparu sont supprimées à leur tour. Cela
 *    n'arrive pas en fonctionnement normal, et c'est bien pour cela qu'il
 *    faut s'en occuper : sinon la galerie affiche une vignette cassée à
 *    tous les invités jusqu'à ce que quelqu'un le remarque.
 *
 * L'ordre compte : jamais l'inverse. Supprimer des fichiers avant les
 * lignes laisserait des vignettes cassées à l'écran.
 */
import { readdir, stat } from "node:fs/promises";
import { join, relative } from "node:path";
import pg from "pg";

const URL_BASE = process.env.JL_DATABASE_URL;
const DOSSIER = process.env.JL_MEDIAS_DIR ?? ".medias";

if (URL_BASE === undefined) {
  console.error("JL_DATABASE_URL est absent : voir .env.example.");
  process.exit(1);
}

const lister = async (racine, dossier = racine) => {
  const trouves = [];
  let entrees;
  try {
    entrees = await readdir(dossier);
  } catch {
    return trouves; // dossier absent : rien à purger
  }
  for (const entree of entrees) {
    const complet = join(dossier, entree);
    if ((await stat(complet)).isDirectory()) trouves.push(...(await lister(racine, complet)));
    else trouves.push(relative(racine, complet));
  }
  return trouves;
};

const client = new pg.Client({ connectionString: URL_BASE });
await client.connect();

const { rows } = await client.query("select tache, lignes from jl.executer_purges()");
for (const ligne of rows) {
  console.log(`${ligne.tache.padEnd(14)} ${ligne.lignes} ligne(s)`);
}

const surDisque = await lister(DOSSIER);
const { rows: connus } = await client.query("select storage_path from public.media");
const references = new Set(connus.map((ligne) => ligne.storage_path));
const orphelins = surDisque.filter((chemin) => !references.has(chemin));

const { rm } = await import("node:fs/promises");
for (const orphelin of orphelins) {
  await rm(join(DOSSIER, orphelin), { force: true });
}
console.log(`${"fichiers".padEnd(14)} ${orphelins.length} orphelin(s) supprimé(s)`);

// Et l'inverse : des lignes dont le fichier n'est plus là.
const restants = new Set(surDisque.filter((chemin) => !orphelins.includes(chemin)));
const perdues = connus.filter((ligne) => !restants.has(ligne.storage_path));
if (perdues.length > 0) {
  await client.query("delete from public.media where storage_path = any($1::text[])", [
    perdues.map((ligne) => ligne.storage_path),
  ]);
}
console.log(`${"lignes".padEnd(14)} ${perdues.length} sans fichier supprimée(s)`);

await client.end();
