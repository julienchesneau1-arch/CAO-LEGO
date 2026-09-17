#!/usr/bin/env node
/**
 * Compose la page de secours statique (brief §0 bis, V0) : le monogramme
 * vectorisé est injecté dans le modèle, sans police ni script. Le résultat
 * est autonome et hébergeable n'importe où.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..");
const genere = readFileSync(join(racine, "components", "monogram.generated.ts"), "utf8");

const viewBox = /MONOGRAMME_VIEWBOX = "([^"]+)"/.exec(genere)?.[1];
const traces = [...genere.matchAll(/\{ lettre: "([^"]+)", d: "([^"]+)" \}/g)].map((m) => m[2]);
if (!viewBox || traces.length === 0) throw new Error("Monogramme généré illisible.");

const [, , largeur, hauteur] = viewBox.split(" ").map(Number);
const hauteurPx = 72;
const largeurPx = Math.round((hauteurPx * (largeur ?? 1)) / (hauteur ?? 1));

const svg = `<svg viewBox="${viewBox}" width="${largeurPx}" height="${hauteurPx}" role="img" aria-label="Julien &amp; Lauriane" focusable="false">
    <g fill="currentColor">${traces.map((d) => `<path d="${d}"/>`).join("")}</g>
  </svg>`;

const modele = readFileSync(join(racine, "secours", "template.html"), "utf8");
if (!modele.includes("<!--MONOGRAMME-->")) throw new Error("Emplacement du monogramme absent du modèle.");

writeFileSync(join(racine, "secours", "index.html"), modele.replace("<!--MONOGRAMME-->", svg));
console.log(`Page de secours composée : secours/index.html (${largeurPx}×${hauteurPx} px de monogramme)`);
