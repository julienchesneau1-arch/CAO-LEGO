#!/usr/bin/env node
/**
 * Vérification bloquante des traductions (brief §5 : aucune chaîne en dur,
 * français et anglais complets). Exécutée avant chaque build : toute clé
 * manquante, en trop ou vide fait échouer la compilation.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "i18n");
const charger = (nom) => JSON.parse(readFileSync(join(racine, nom), "utf8"));

const aplatir = (objet, prefixe = "") =>
  Object.entries(objet).flatMap(([cle, valeur]) => {
    const chemin = prefixe ? `${prefixe}.${cle}` : cle;
    return typeof valeur === "object" && valeur !== null
      ? aplatir(valeur, chemin)
      : [[chemin, valeur]];
  });

const fr = new Map(aplatir(charger("fr.json")));
const en = new Map(aplatir(charger("en.json")));

const erreurs = [];
for (const cle of fr.keys()) if (!en.has(cle)) erreurs.push(`en.json : clé manquante « ${cle} »`);
for (const cle of en.keys()) if (!fr.has(cle)) erreurs.push(`en.json : clé en trop « ${cle} »`);
for (const [nom, table] of [["fr.json", fr], ["en.json", en]]) {
  for (const [cle, valeur] of table) {
    if (typeof valeur !== "string") erreurs.push(`${nom} : « ${cle} » n'est pas une chaîne`);
    else if (valeur.trim() === "") erreurs.push(`${nom} : « ${cle} » est vide`);
  }
}

if (erreurs.length > 0) {
  console.error("Traductions incomplètes :");
  for (const e of erreurs) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`Traductions vérifiées : ${fr.size} clés, fr et en alignés.`);
