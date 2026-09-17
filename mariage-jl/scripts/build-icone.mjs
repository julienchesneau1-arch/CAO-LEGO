#!/usr/bin/env node
/**
 * Icône de l'application (onglet du navigateur, écran d'accueil du téléphone).
 * Générée depuis les mêmes tracés que le monogramme : un seul dessin, partout.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..");
const genere = readFileSync(join(racine, "components", "monogram.generated.ts"), "utf8");
const viewBox = /MONOGRAMME_VIEWBOX = "([^"]+)"/.exec(genere)?.[1];
const traces = [...genere.matchAll(/\{ lettre: "([^"]+)", d: "([^"]+)" \}/g)].map((m) => m[2]);
if (!viewBox || traces.length === 0) throw new Error("Monogramme généré illisible.");

const [x, y, largeur, hauteur] = viewBox.split(" ").map(Number);
// Carré centré autour du monogramme, fond noir de la direction artistique.
const cote = Math.max(largeur ?? 1, hauteur ?? 1) * 1.25;
const decalageX = (x ?? 0) - ((cote - (largeur ?? 0)) / 2);
const decalageY = (y ?? 0) - ((cote - (hauteur ?? 0)) / 2);

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${decalageX.toFixed(2)} ${decalageY.toFixed(2)} ${cote.toFixed(2)} ${cote.toFixed(2)}">
  <rect x="${decalageX.toFixed(2)}" y="${decalageY.toFixed(2)}" width="${cote.toFixed(2)}" height="${cote.toFixed(2)}" fill="#080808"/>
  <g fill="#E9E2D8">${traces.map((d) => `<path d="${d}"/>`).join("")}</g>
</svg>
`;
writeFileSync(join(racine, "app", "icon.svg"), svg);
console.log("app/icon.svg généré");
