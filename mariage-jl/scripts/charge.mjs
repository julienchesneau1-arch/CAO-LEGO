#!/usr/bin/env node
/**
 * Test de charge (brief §10) : « 150 invités ouvrant l'app en 5 minutes,
 * 50 envois de photos simultanés, 20 vidéos de 200 Mo ».
 *
 * Ce script mesure, il ne conclut pas. Il affiche les percentiles observés
 * et le nombre d'échecs ; c'est le rapport écrit qui juge, comme le demande
 * le brief.
 *
 * IMPORTANT — ce qu'il ne faut pas faire avec :
 * — ne pas le lancer pendant la période de gel (§17) ;
 * — ne pas le lancer sur la production au moment où des invités l'utilisent ;
 * — les foyers d'essai qu'il crée portent l'étiquette « CHARGE — » et sont
 *   supprimés à la fin, y compris en cas d'interruption.
 *
 * Usage :
 *   JL_DATABASE_URL=... node scripts/charge.mjs http://127.0.0.1:3000
 *   JL_DATABASE_URL=... node scripts/charge.mjs https://… --foyers 150 --photos 50
 */
import { createHash, randomBytes } from "node:crypto";
import pg from "pg";

const base = process.argv[2];
if (base === undefined || !base.startsWith("http")) {
  console.error("Usage : node scripts/charge.mjs <adresse> [--foyers 150] [--photos 50]");
  process.exit(1);
}
if (process.env.JL_DATABASE_URL === undefined) {
  console.error("JL_DATABASE_URL est absent : le script doit créer des foyers d'essai.");
  process.exit(1);
}

const nombre = (nom, defaut) => {
  const index = process.argv.indexOf(`--${nom}`);
  if (index === -1) return defaut;
  const valeur = Number(process.argv[index + 1]);
  return Number.isFinite(valeur) && valeur > 0 ? Math.floor(valeur) : defaut;
};

const FOYERS = nombre("foyers", 150);
const PHOTOS = nombre("photos", 50);
/** Le brief dit « en 5 minutes » : on étale les ouvertures sur cette fenêtre. */
const FENETRE_MS = nombre("fenetre", 300) * 1000;
const ETIQUETTE = "CHARGE — ";

const ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789";
const jeton = () => Array.from(randomBytes(32), (o) => ALPHABET[o % ALPHABET.length]).join("");
const empreinte = (secret) =>
  createHash("sha256").update(secret.trim().toLowerCase(), "utf8").digest();

const client = new pg.Client({ connectionString: process.env.JL_DATABASE_URL });
await client.connect();

/** Nettoyage systématique, y compris si on interrompt au clavier. */
let nettoye = false;
const nettoyer = async () => {
  if (nettoye) return;
  nettoye = true;
  const { rowCount } = await client.query(
    "delete from public.households where label_public like $1",
    [`${ETIQUETTE}%`],
  );
  console.log(`\nNettoyage : ${rowCount} foyer(s) d'essai supprimé(s).`);
  await client.end().catch(() => undefined);
};
process.on("SIGINT", async () => {
  await nettoyer();
  process.exit(130);
});

/** Un JPEG minimal mais valide, de la taille demandée. */
function jpegDe(octets) {
  const donnees = new Uint8Array(Math.max(32, octets));
  donnees.set([0xff, 0xd8, 0xff, 0xdb, 0x00, 0x05, 0x00, 0x01, 0x02], 0);
  // Le marqueur de données compressées, puis du remplissage.
  donnees.set([0xff, 0xda, 0x00, 0x04, 0x01, 0x02], 9);
  for (let index = 15; index < donnees.length; index += 1) donnees[index] = (index * 7) % 251;
  return donnees;
}

const percentile = (valeurs, part) => {
  if (valeurs.length === 0) return undefined;
  const triees = [...valeurs].sort((a, b) => a - b);
  const rang = Math.min(triees.length - 1, Math.floor(part * triees.length));
  return Math.round(triees[rang]);
};

const rapport = (nom, durees, echecs) => {
  const ligne = (libelle, valeur) =>
    `  ${libelle.padEnd(12)} ${valeur === undefined ? "—" : `${valeur} ms`}`;
  console.log(`\n${nom} — ${durees.length} réussite(s), ${echecs} échec(s)`);
  console.log(ligne("médiane", percentile(durees, 0.5)));
  console.log(ligne("p90", percentile(durees, 0.9)));
  console.log(ligne("p99", percentile(durees, 0.99)));
  console.log(ligne("maximum", durees.length === 0 ? undefined : Math.round(Math.max(...durees))));
};

try {
  // ------------------------------------------------- Ouvertures étalées
  console.log(`Création de ${FOYERS} foyers d'essai…`);
  const jetons = [];
  for (let index = 0; index < FOYERS; index += 1) {
    const secret = jeton();
    await client.query(
      `insert into public.households (label_public, token_sha256, backup_code_sha256)
       values ($1, $2, $3)`,
      [`${ETIQUETTE}${index + 1}`, empreinte(secret), empreinte(`${secret}-code`)],
    );
    jetons.push(secret);
  }

  console.log(`Ouverture de ${FOYERS} invitations étalées sur ${FENETRE_MS / 1000} s…`);
  const ouvertures = [];
  let echecsOuverture = 0;
  const pas = FENETRE_MS / FOYERS;

  await Promise.all(
    jetons.map(async (secret, index) => {
      await new Promise((r) => setTimeout(r, index * pas));
      const depart = performance.now();
      try {
        // `redirect: manual` : on mesure la réponse du serveur, pas la
        // navigation complète qu'un navigateur enchaînerait ensuite.
        const reponse = await fetch(`${base}/i/${secret}`, { redirect: "manual" });
        if (reponse.status >= 400) throw new Error(`statut ${reponse.status}`);
        ouvertures.push(performance.now() - depart);
      } catch {
        echecsOuverture += 1;
      }
    }),
  );
  rapport("Ouverture de l'invitation", ouvertures, echecsOuverture);

  // -------------------------------------------- Envois de photos simultanés
  console.log(`\nEnvoi de ${PHOTOS} photos simultanées…`);
  const utilises = jetons.slice(0, PHOTOS);
  // Le consentement est posé en base : le test mesure l'envoi, pas le
  // parcours de consentement, déjà couvert par les tests fonctionnels.
  await client.query(
    `insert into public.media_consent (household_id, consent_text_version)
     select id, 'charge' from public.households where label_public like $1
     on conflict (household_id) do nothing`,
    [`${ETIQUETTE}%`],
  );

  const image = jpegDe(1_500_000); // 1,5 Mo : une photo compressée par le navigateur
  const envois = [];
  let echecsEnvoi = 0;

  await Promise.all(
    utilises.map(async (secret) => {
      const depart = performance.now();
      try {
        // Un envoi part avec le cookie du foyer : on ouvre d'abord.
        const ouverture = await fetch(`${base}/i/${secret}`, { redirect: "manual" });
        const cookie = (ouverture.headers.getSetCookie?.() ?? [])
          .map((entree) => entree.split(";")[0])
          .join("; ");

        const corps = new FormData();
        corps.append("fichier", new Blob([image], { type: "image/jpeg" }), "charge.jpg");
        const reponse = await fetch(`${base}/photos/televerser`, {
          method: "POST",
          headers: cookie === "" ? {} : { cookie },
          body: corps,
        });
        if (!reponse.ok) throw new Error(`statut ${reponse.status}`);
        envois.push(performance.now() - depart);
      } catch {
        echecsEnvoi += 1;
      }
    }),
  );
  rapport("Envoi d'une photo de 1,5 Mo", envois, echecsEnvoi);

  // ---------------------------------------------------- Écrans de contenu
  console.log("\nLecture des écrans de contenu…");
  for (const chemin of ["/programme", "/infos", "/faq", "/aide", "/photos"]) {
    const durees = [];
    let echecs = 0;
    await Promise.all(
      Array.from({ length: 30 }, async () => {
        const depart = performance.now();
        try {
          const reponse = await fetch(`${base}${chemin}`);
          if (!reponse.ok) throw new Error(`statut ${reponse.status}`);
          await reponse.text();
          durees.push(performance.now() - depart);
        } catch {
          echecs += 1;
        }
      }),
    );
    rapport(`${chemin} (30 en parallèle)`, durees, echecs);
  }

  console.log(
    "\nÀ consigner dans le rapport écrit du brief §10 : ces chiffres, la machine, la date, et ce qui a gêné.",
  );
} finally {
  await nettoyer();
}
