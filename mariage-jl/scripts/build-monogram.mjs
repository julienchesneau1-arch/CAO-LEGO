#!/usr/bin/env node
/**
 * Vectorise le monogramme (brief §3) : J et L en Bodoni Moda romain,
 * & en Bodoni Moda italique à 95 %, ligne de base commune.
 * Résultat figé dans components/monogram.generated.ts : à l'exécution, le
 * monogramme est un tracé SVG, il ne dépend plus du rendu des polices.
 *
 * ÉCART CONNU : l'API Google Fonts sert une police variable dont l'axe wght
 * vaut 400 par défaut. opentype.js n'interpole pas les axes variables : les
 * tracés sont donc en wght 400, alors que le brief demande ≈ 470. Le texte
 * vivant, lui, est rendu en 470 via font-variation-settings. Voir V0-11.
 *
 * Relancer uniquement si les axes changent : `pnpm run gen:monogram`.
 */
import { writeFileSync } from "node:fs";
import opentype from "opentype.js";
import { decompress } from "wawoff2";

const CSS =
  "https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,24,470;1,24,470";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
const TAILLE = 1000;
const RATIO_ITALIQUE = 0.95;
const ECART = 0.055 * TAILLE; // espace optique entre les tracés

/** Le sous-ensemble « latin » est celui qui contient J, & et L. */
const LATIN = "U+0000-00FF";

async function charger(url, entetes = {}) {
  const r = await fetch(url, { headers: { "User-Agent": UA, ...entetes } });
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r;
}

function blocsFontFace(css) {
  return css
    .split("@font-face")
    .slice(1)
    .map((bloc) => ({
      style: /font-style:\s*([\w-]+)/.exec(bloc)?.[1] ?? "normal",
      poids: /font-weight:\s*([\d.]+)/.exec(bloc)?.[1] ?? "400",
      plage: /unicode-range:\s*([^;]+)/.exec(bloc)?.[1]?.trim() ?? "",
      url: /url\((https:[^)]+)\)/.exec(bloc)?.[1],
    }))
    .filter((b) => b.url !== undefined);
}

async function police(url) {
  const reponse = await charger(url);
  const brut = new Uint8Array(await reponse.arrayBuffer());
  const ttf = new Uint8Array(await decompress(brut));
  const tampon = new ArrayBuffer(ttf.length);
  new Uint8Array(tampon).set(ttf);
  return opentype.parse(tampon);
}

const css = await (await charger(CSS)).text();
const blocs = blocsFontFace(css);
const choisir = (style) => {
  const exact = blocs.find((b) => b.style === style && b.plage.startsWith(LATIN));
  return exact ?? blocs.find((b) => b.style === style);
};

const romainBloc = choisir("normal");
const italiqueBloc = choisir("italic");
if (!romainBloc?.url || !italiqueBloc?.url) {
  throw new Error("Sous-ensembles latin introuvables dans la réponse de l'API Google Fonts.");
}

const romain = await police(romainBloc.url);
const italique = await police(italiqueBloc.url);

function trace(font, caractere, taille) {
  const glyphe = font.charToGlyph(caractere);
  if (glyphe.unicode === undefined) throw new Error(`Glyphe absent : ${caractere}`);
  const chemin = glyphe.getPath(0, 0, taille);
  return { chemin, boite: chemin.getBoundingBox() };
}

const pieces = [
  { lettre: "J", ...trace(romain, "J", TAILLE) },
  { lettre: "&", ...trace(italique, "&", TAILLE * RATIO_ITALIQUE) },
  { lettre: "L", ...trace(romain, "L", TAILLE) },
];

/**
 * Composition sur une ligne de base commune (y = 0) : les tracés sont placés
 * au bord optique (boîte englobante) et non à l'avance métrique, ce qui donne
 * un monogramme resserré plutôt qu'un mot.
 */
let curseur = 0;
const traces = [];
for (const [index, piece] of pieces.entries()) {
  const decalage = curseur - piece.boite.x1;
  const commandes = piece.chemin.commands.map((commande) => {
    const copie = { ...commande };
    for (const cle of ["x", "x1", "x2"]) {
      if (typeof copie[cle] === "number") copie[cle] += decalage;
    }
    return copie;
  });
  const chemin = new opentype.Path();
  chemin.commands = commandes;
  traces.push({ lettre: piece.lettre, d: chemin.toPathData(2) });
  curseur += piece.boite.x2 - piece.boite.x1 + (index < pieces.length - 1 ? ECART : 0);
}

const yMin = Math.min(...pieces.map((p) => p.boite.y1));
const yMax = Math.max(...pieces.map((p) => p.boite.y2));
const marge = TAILLE * 0.03;
const viewBox = [
  (-marge).toFixed(2),
  (yMin - marge).toFixed(2),
  (curseur + marge * 2).toFixed(2),
  (yMax - yMin + marge * 2).toFixed(2),
].join(" ");

const axes = (font) =>
  font.tables.fvar
    ? font.tables.fvar.axes.map((a) => `${a.tag}=${a.defaultValue}`).join(", ")
    : "instance statique";

const sortie = `// Fichier généré par scripts/build-monogram.mjs — ne pas modifier à la main.
// Bodoni Moda : J et L romains, & italique à ${RATIO_ITALIQUE * 100} %, ligne de base commune.
// Axes réellement servis — romain : ${axes(romain)} ; italique : ${axes(italique)}.
// ÉCART : le brief demande wght ≈ 470 ; opentype.js n'interpole pas les axes
// variables, ces tracés sont donc en wght 400 (question V0-11).
// Généré le ${new Date().toISOString().slice(0, 10)} depuis l'API Google Fonts.

export const MONOGRAMME_VIEWBOX = "${viewBox}";

export const MONOGRAMME_TRACES: ReadonlyArray<{ lettre: string; d: string }> = [
${traces.map((t) => `  { lettre: "${t.lettre}", d: "${t.d}" },`).join("\n")}
];
`;

writeFileSync(new URL("../components/monogram.generated.ts", import.meta.url), sortie);
console.log(`Monogramme vectorisé : ${traces.length} tracés, viewBox ${viewBox}`);
console.log(`Romain   : ${romainBloc.url}`);
console.log(`Italique : ${italiqueBloc.url}`);
