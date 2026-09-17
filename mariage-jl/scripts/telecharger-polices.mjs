#!/usr/bin/env node
/**
 * Télécharge les sous-ensembles latins de Bodoni Moda et Cormorant Garamond
 * et les dépose dans assets/polices/.
 *
 * Pourquoi des fichiers dans le dépôt plutôt que `next/font/google` :
 * 1. la compilation ne dépend plus du réseau (utile en intégration continue
 *    et pendant le gel de J-7 à J+1) ;
 * 2. Next connaît alors les URL à l'avance et émet le `preload` des polices,
 *    ce qui faisait perdre deux secondes de LCP sur l'accueil.
 *
 * Licence : les deux familles sont sous SIL Open Font License 1.1. Les URL
 * d'origine sont consignées dans assets/polices/SOURCES.md.
 *
 * Usage : pnpm run polices   (à relancer seulement si les axes changent)
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const DOSSIER = join(dirname(fileURLToPath(import.meta.url)), "..", "assets", "polices");
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const FAMILLES = [
  {
    fichier: "bodoni-moda-latin.woff2",
    css: "https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,400..900",
    style: "normal",
  },
  {
    fichier: "bodoni-moda-italique-latin.woff2",
    css: "https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@1,6..96,400..900",
    style: "italic",
  },
  {
    fichier: "cormorant-garamond-latin.woff2",
    css: "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300..700",
    style: "normal",
  },
];

const sources = ["# Polices — sources et licence", "", "SIL Open Font License 1.1.", ""];

for (const famille of FAMILLES) {
  const css = await (await fetch(famille.css, { headers: { "User-Agent": UA } })).text();
  const blocs = css.split("@font-face").slice(1);
  const latin = blocs.find(
    (bloc) =>
      /unicode-range:\s*U\+0000-00FF/.test(bloc) &&
      new RegExp(`font-style:\\s*${famille.style}`).test(bloc),
  );
  const url = /url\((https:[^)]+)\)/.exec(latin ?? "")?.[1];
  if (url === undefined) throw new Error(`Sous-ensemble latin introuvable pour ${famille.fichier}`);

  const octets = new Uint8Array(
    await (await fetch(url, { headers: { "User-Agent": UA } })).arrayBuffer(),
  );
  writeFileSync(join(DOSSIER, famille.fichier), octets);
  console.log(`${famille.fichier} : ${(octets.length / 1024).toFixed(1)} ko`);
  sources.push(`- \`${famille.fichier}\` — ${url}`);
}

sources.push(
  "",
  `Téléchargées le ${new Date().toISOString().slice(0, 10)} via l'API Google Fonts.`,
  "",
  "Si l'application devient publique au-delà du cercle des invités, joindre le",
  "texte complet de la licence OFL 1.1 à ce dossier.",
);
writeFileSync(join(DOSSIER, "SOURCES.md"), `${sources.join("\n")}\n`);
