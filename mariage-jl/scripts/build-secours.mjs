#!/usr/bin/env node
/**
 * Compose la page de secours statique (brief §0 bis, V0 ; §10, plan B).
 *
 * Le monogramme vectorisé est injecté dans le modèle, sans police ni
 * script : le résultat est autonome et hébergeable n'importe où.
 *
 * Le contenu — horaires, adresse, date limite, numéros — est **lu dans la
 * base** quand elle est joignable. C'est ce qui empêche la page de secours
 * de vieillir : elle est régénérée à chaque livraison, et elle dit alors la
 * même chose que l'application. Sans base, les mentions « [À COMPLÉTER] »
 * restent en place — jamais une valeur inventée (règle 2).
 *
 * Le jour où elle doit servir, elle sert : c'est le seul écran qui marche
 * quand plus rien ne marche.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..");
const ATTENTE = "[À COMPLÉTER]";

/** Échappe le texte : il vient de la base, donc d'une saisie humaine. */
const echapper = (valeur) =>
  String(valeur)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const ecrit = (valeur) =>
  typeof valeur === "string" &&
  valeur.trim() !== "" &&
  !valeur.includes(ATTENTE) &&
  !valeur.includes("[TO BE COMPLETED]");

const doux = (valeur) => `<span class="doux">${echapper(valeur)}</span>`;

// ------------------------------------------------------------ Monogramme
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

// --------------------------------------------------------------- Contenu
/** Les cinq moments, dans leur couleur officielle (brief §2). */
const COULEURS = {
  "01": "#E9B131",
  "02": "#365D87",
  "03": "#CB5726",
  "04": "#721F23",
  "05": "#84568D",
};
const AMORCE = [
  { id: "01", nom: "L’Éclat", genre: "Accueil" },
  { id: "02", nom: "L’Horizon", genre: "Cérémonie" },
  { id: "03", nom: "La Rencontre", genre: "Cocktail" },
  { id: "04", nom: "L’Ivresse", genre: "Dîner" },
  { id: "05", nom: "La Nuit", genre: "Fête" },
];

let donnees;
if (process.env.JL_DATABASE_URL !== undefined) {
  const pg = (await import("pg")).default;
  const client = new pg.Client({ connectionString: process.env.JL_DATABASE_URL });
  try {
    await client.connect();
    const moments = await client.query(
      `select id, name_fr as nom, kind_fr as genre, place,
              to_char(starts_at at time zone 'Europe/Paris', 'HH24:MI') as debut,
              to_char(ends_at   at time zone 'Europe/Paris', 'HH24:MI') as fin
         from public.moments order by id`,
    );
    const blocs = await client.query(
      "select key, value from public.content_blocks where locale = 'fr'",
    );
    const parametres = await client.query(
      "select to_char(date_limite_reponse, 'DD/MM/YYYY') as limite from public.parametres where id = 1",
    );
    donnees = {
      moments: moments.rows,
      blocs: Object.fromEntries(blocs.rows.map((ligne) => [ligne.key, ligne.value])),
      limite: parametres.rows[0]?.limite ?? null,
    };
    console.log("Contenu lu dans la base : la page de secours dit la même chose que l’application.");
  } catch (erreur) {
    console.log(`Base injoignable (${erreur.message}) — les mentions « ${ATTENTE} » restent.`);
  } finally {
    await client.end().catch(() => undefined);
  }
} else {
  console.log(`JL_DATABASE_URL absent — les mentions « ${ATTENTE} » restent.`);
}

const moments = donnees?.moments ?? AMORCE;
const blocs = donnees?.blocs ?? {};

const programme = `<ul>
${moments
  .map((moment) => {
    const horaire =
      moment.debut == null
        ? doux(ATTENTE)
        : `<span class="doux">${moment.fin == null ? `à partir de ${moment.debut}` : `de ${moment.debut} à ${moment.fin}`}</span>`;
    const lieu = ecrit(moment.place) ? ` · ${echapper(moment.place)}` : "";
    return `      <li>${moment.id} · ${echapper(moment.nom)} — ${echapper(moment.genre)} ${horaire}${lieu}<span class="fil" style="background:${COULEURS[moment.id] ?? "#8A8578"}"></span></li>`;
  })
  .join("\n")}
    </ul>`;

const venir = `<p>Domaine de Roiffé, 86120 Roiffé (Vienne)</p>
    <p>${ecrit(blocs["infos.venir"]?.texte) ? echapper(blocs["infos.venir"].texte) : `Accès et stationnement : ${doux(ATTENTE)}`}</p>`;

const repondre = `<p>Date limite de réponse : ${
  donnees?.limite == null ? doux(ATTENTE) : echapper(donnees.limite)
}</p>
    <p class="doux">Répondez depuis le QR code de votre faire-part. Si l’application est indisponible, appelez-nous.</p>`;

/**
 * Les numéros de l'écran Aide : c'est ce qu'on cherche quand rien ne marche.
 * Un numéro absent n'affiche pas de lien mort.
 */
const contacts = (() => {
  const lignes = [];
  for (const [cle, role] of [
    ["aide.regie", "L’équipe du jour"],
    ["aide.temoin", "Un témoin"],
  ]) {
    const bloc = blocs[cle];
    const numero = bloc?.telephone;
    if (typeof numero === "string" && numero.trim() !== "") {
      const compose = numero.replace(/[\s.\-()]/g, "");
      lignes.push(
        `<p>${role} · ${echapper(bloc.texte ?? "")} — <a class="action" href="tel:${echapper(compose)}">${echapper(numero)}</a></p>`,
      );
    }
  }
  if (lignes.length === 0) lignes.push(`<p>Contact : ${doux(ATTENTE)}</p>`);
  const wifi = blocs["jour.wifi"]?.texte;
  if (ecrit(wifi)) lignes.push(`<p>Wi-Fi des invités : ${echapper(wifi)}</p>`);
  return lignes.join("\n    ");
})();

// ---------------------------------------------------------------- Montage
let page = readFileSync(join(racine, "secours", "template.html"), "utf8");
for (const [marque, contenu] of [
  ["<!--MONOGRAMME-->", svg],
  ["<!--PROGRAMME-->", programme],
  ["<!--VENIR-->", venir],
  ["<!--REPONDRE-->", repondre],
  ["<!--CONTACTS-->", contacts],
]) {
  if (!page.includes(marque)) throw new Error(`Emplacement ${marque} absent du modèle.`);
  page = page.replace(marque, contenu);
}

writeFileSync(join(racine, "secours", "index.html"), page);
const restantes = (page.match(/\[À COMPLÉTER\]/g) ?? []).length;
console.log(
  `Page de secours composée : secours/index.html — ${restantes} mention(s) « ${ATTENTE} » restante(s).`,
);
