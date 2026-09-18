#!/usr/bin/env node
/**
 * Captures d'écran mobile exigées à chaque livraison (brief §0, méthode 2).
 * Téléphone simulé : 390 × 844. Le script pose son propre foyer de
 * démonstration dans la base de développement, prend les captures, puis le
 * supprime : aucune donnée réelle, aucun reste.
 *
 * Prérequis : ./scripts/pg-local.sh start && pnpm db:seed && pnpm build
 */
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { chromium, devices } from "@playwright/test";
import pg from "pg";

const PORT = Number(process.env["PORT"] ?? 3210);
const BASE = `http://127.0.0.1:${PORT}`;
const URL_BASE_DONNEES =
  process.env["JL_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/jl_dev";
const DOSSIER = new URL("../captures/", import.meta.url);
mkdirSync(DOSSIER, { recursive: true });

// Dossier jetable des souvenirs de démonstration : jamais celui du
// développement, et vidé à la fin.
const MEDIAS = "/tmp/jl-captures-medias";
rmSync(MEDIAS, { recursive: true, force: true });
mkdirSync(MEDIAS, { recursive: true });

const ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789";
const jeton = Array.from(randomBytes(32), (o) => ALPHABET[o % ALPHABET.length]).join("");
const empreinte = (s) => createHash("sha256").update(s.trim().toLowerCase(), "utf8").digest();

const base = new pg.Client({ connectionString: URL_BASE_DONNEES });
await base.connect();
// Le dossier des souvenirs vient d'être vidé : les lignes de la série
// précédente n'ont plus de fichier et afficheraient des vignettes cassées.
await base.query("delete from public.media");
const { rows } = await base.query(
  `insert into public.households (label_public, token_sha256, backup_code_sha256)
   values ('Foyer de démonstration', $1, $2) returning id`,
  [empreinte(jeton), empreinte("DEMO01")],
);
const foyerId = rows[0].id;
await base.query(
  `insert into public.guests (household_id, first_name, sort_order)
   values ($1, 'Prénom A', 0), ($1, 'Prénom B', 1)`,
  [foyerId],
);

// Un accès administrateur jetable, pour photographier l'espace des mariés.
const jetonAdmin = Array.from(randomBytes(32), (o) => ALPHABET[o % ALPHABET.length]).join("");
const emailAdmin = "demonstration@exemple.test";
await base.query(
  `insert into public.admin_users (email, role) values ($1, 'admin')
   on conflict (email) do update set revoked_at = null`,
  [emailAdmin],
);
await base.query(
  `insert into public.admin_magic_links (email, token_sha256, expires_at)
   values ($1, $2, now() + interval '30 minutes')`,
  [emailAdmin, empreinte(jetonAdmin)],
);

const serveur = spawn("node", [".next/standalone/server.js"], {
  env: {
    ...process.env,
    PORT: String(PORT),
    HOSTNAME: "127.0.0.1",
    JL_DATABASE_URL: URL_BASE_DONNEES,
    // Le serveur compilé tourne en NODE_ENV=production : le secret de cookie
    // est alors obligatoire (c'est voulu). On en tire un, jetable.
    JL_COOKIE_SECRET: process.env["JL_COOKIE_SECRET"] ?? randomBytes(32).toString("base64url"),
    JL_PROMESSE_CLE_PUBLIQUE: process.env["JL_PROMESSE_CLE_PUBLIQUE"] ?? "",
    JL_MEDIAS_DIR: MEDIAS,
  },
  cwd: new URL("..", import.meta.url).pathname,
  stdio: "ignore",
});

/** Journée simulée autour de maintenant, pour photographier « Maintenant ». */
const poserJourneeEtPeriode = async (enCours, periode) => {
  const ordre = ["01", "02", "03", "04", "05"];
  const rang = ordre.indexOf(enCours);
  for (const [index, id] of ordre.entries()) {
    const debut = (index - rang) * 60 - 10;
    await base.query(
      `update public.moments
          set starts_at = now() + ($2 || ' minutes')::interval,
              ends_at   = now() + ($3 || ' minutes')::interval
        where id = $1`,
      [id, String(debut), String(debut + 60)],
    );
  }
  await base.query(
    `update public.parametres
        set periode_forcee = $1, periode_forcee_jusqu_a = now() + interval '1 hour'
      where id = 1`,
    [periode],
  );
};

/** Une table de démonstration, avec les deux invités du foyer dessus. */
const poserUneTable = async () => {
  const { rows: tables } = await base.query(
    `insert into public.seating_tables (label, capacity, sort_order)
     values ('Table des vignes', 8, 1)
     on conflict (label) do update set capacity = 8 returning id`,
  );
  await base.query(
    `insert into public.seating_assign (guest_id, table_id)
     select id, $1 from public.guests where household_id = $2
     on conflict (guest_id) do update set table_id = excluded.table_id`,
    [tables[0].id, foyerId],
  );
};

const attendre = async () => {
  for (let essai = 0; essai < 60; essai += 1) {
    try {
      const r = await fetch(`${BASE}/api/health`);
      if (r.ok) return;
    } catch {
      /* le serveur démarre encore */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Le serveur ne répond pas ou la base est injoignable.");
};

try {
  await attendre();
  const chemin = process.env["JL_CHROMIUM"] ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const navigateur = await chromium.launch(existsSync(chemin) ? { executablePath: chemin } : {});
  const contexte = await navigateur.newContext({
    ...devices["iPhone 13"],
    deviceScaleFactor: 1,
    locale: "fr-FR",
    timezoneId: "Europe/Paris",
  });
  const page = await contexte.newPage();
  /**
   * `attente` sert à photographier une animation en cours ; `pageEntiere` est
   * faux pour les écrans en surcouche, qui ne couvrent que la fenêtre.
   */
  const prendre = async (nom, { attente = 1100, pageEntiere = true } = {}) => {
    await page.waitForTimeout(attente);
    await page.screenshot({
      path: new URL(`${nom}.jpg`, DOSSIER).pathname,
      type: "jpeg",
      quality: 75,
      fullPage: pageEntiere,
    });
    console.log(`capture : ${nom}.jpg`);
  };

  // Ouverture par QR : premier lancement en trois écrans.
  await page.goto(`${BASE}/i/${jeton}`, { waitUntil: "networkidle" });
  await prendre("01-ouverture-signature", { attente: 550, pageEntiere: false });
  await page.getByRole("button", { name: "Continuer" }).click();
  await prendre("02-confort-de-lecture", { pageEntiere: false });
  await page.getByRole("button", { name: "Continuer" }).click();
  await prendre("03-bienvenue", { pageEntiere: false });
  await page.getByRole("button", { name: "Tout est ici." }).click();
  await prendre("04-accueil-foyer-reconnu");

  // Confort de lecture « très grande » sur l'accueil.
  await page.evaluate(() =>
    localStorage.setItem(
      "jl_confort",
      JSON.stringify({ taille: "tres-grande", papier: "non", mouvement: "normal" }),
    ),
  );
  await page.reload({ waitUntil: "networkidle" });
  await prendre("05-accueil-tres-grande");

  await page.evaluate(() => localStorage.removeItem("jl_confort"));
  await page.goto(`${BASE}/retrouver`, { waitUntil: "networkidle" });
  await prendre("06-retrouver-mon-invitation");

  await page.goto(`${BASE}/partager`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Créer un lien" }).click();
  await page.waitForLoadState("networkidle");
  await prendre("07-partager-l-acces");

  await page.goto(`${BASE}/programme`, { waitUntil: "networkidle" });
  await prendre("08-programme");

  await page.goto(`${BASE}/programme/02`, { waitUntil: "networkidle" });
  await prendre("09-deroule-du-moment");

  await page.goto(`${BASE}/infos`, { waitUntil: "networkidle" });
  await prendre("10-infos");

  await page.goto(`${BASE}/faq`, { waitUntil: "networkidle" });
  await prendre("11-faq");

  await page.goto(`${BASE}/reponse`, { waitUntil: "networkidle" });
  await prendre("12-reponse-question");
  await page.getByRole("button", { name: "Oui", exact: true }).click();
  await page.waitForLoadState("networkidle");
  await prendre("13-reponse-details");

  // Espace des mariés : le lien magique ouvre la session, puis on photographie.
  await page.goto(`${BASE}/admin/entrer?jeton=${jetonAdmin}`, { waitUntil: "networkidle" });
  await prendre("14-admin-tableau-de-bord");
  await page.goto(`${BASE}/admin/invites`, { waitUntil: "networkidle" });
  await prendre("15-admin-invites");

  // « Contenus » : c'est d'ici que les mariés remplacent chaque
  // « [À COMPLÉTER] » par le vrai texte, sans passer par du SQL.
  await page.goto(`${BASE}/admin/contenus?section=journee`, { waitUntil: "networkidle" });
  await prendre("22-admin-contenus-journee");
  await page.goto(`${BASE}/admin/contenus?section=moments`, { waitUntil: "networkidle" });
  await prendre("23-admin-contenus-moments");
  await page.goto(`${BASE}/admin/contenus?section=moments&element=02`, {
    waitUntil: "networkidle",
  });
  await prendre("24-admin-contenus-un-moment");
  await page.goto(`${BASE}/admin/contenus?section=faq`, { waitUntil: "networkidle" });
  await prendre("25-admin-contenus-faq");
  await page.goto(`${BASE}/admin/contenus?section=hebergements&element=nouveau`, {
    waitUntil: "networkidle",
  });
  await prendre("27-admin-contenus-hebergement");
  await page.goto(`${BASE}/admin/contenus?section=contacts`, { waitUntil: "networkidle" });
  await prendre("26-admin-contenus-contacts");
  await page.goto(`${BASE}/admin/annonces`, { waitUntil: "networkidle" });
  await prendre("28-admin-annonces");
  await page.goto(`${BASE}/regie`, { waitUntil: "networkidle" });
  await prendre("29-regie");

  await page.goto(`${BASE}/design`, { waitUntil: "networkidle" });
  await prendre("16-direction-artistique");

  await page.goto(`${BASE}/le-texte`, { waitUntil: "networkidle" });
  await prendre("18-le-texte", { attente: 2600 });
  await page.getByRole("button", { name: "Sauf que…" }).click();
  await prendre("19-le-texte-sauf-que", { attente: 2600 });

  await page.goto(`${BASE}/promesse`, { waitUntil: "networkidle" });
  await prendre("20-la-promesse");

  await page.goto(`${BASE}/loin`, { waitUntil: "networkidle" });
  await prendre("21-ceux-qui-sont-loin");

  await page.goto(`${BASE}/aide`, { waitUntil: "networkidle" });
  await prendre("30-aide");

  /**
   * Les souvenirs passent par le vrai parcours : accord, puis envoi d'une
   * image dessinée dans le navigateur. Une capture d'un écran vide
   * n'apprendrait rien, et une insertion directe en base ne prouverait pas
   * que le chemin d'envoi fonctionne.
   */
  await page.goto(`${BASE}/photos/envoyer`, { waitUntil: "networkidle" });
  await prendre("34-partager-un-souvenir-accord");
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await page.waitForLoadState("networkidle");

  for (const couleur of ["#c8452a", "#1f4e79", "#e0a43c", "#7d2a3a", "#8f7bb5", "#2f6f4f"]) {
    const octets = await page.evaluate(async (teinte) => {
      const toile = document.createElement("canvas");
      toile.width = 600;
      toile.height = 450;
      const ctx = toile.getContext("2d");
      ctx.fillStyle = teinte;
      ctx.fillRect(0, 0, 600, 450);
      ctx.fillStyle = "rgba(233, 226, 216, 0.25)";
      ctx.fillRect(40, 40, 520, 370);
      const blob = await new Promise((r) => toile.toBlob(r, "image/jpeg", 0.9));
      return [...new Uint8Array(await blob.arrayBuffer())];
    }, couleur);
    await page.setInputFiles('input[type="file"]', {
      name: `souvenir-${couleur.slice(1)}.jpg`,
      mimeType: "image/jpeg",
      buffer: Buffer.from(octets),
    });
    await page.waitForTimeout(400);
  }
  await prendre("35-partager-un-souvenir");

  await page.goto(`${BASE}/photos`, { waitUntil: "networkidle" });
  await prendre("36-les-souvenirs");

  await poserUneTable();
  await page.goto(`${BASE}/ma-table`, { waitUntil: "networkidle" });
  await prendre("37-ma-table");

  await page.goto(`${BASE}/admin/table`, { waitUntil: "networkidle" });
  await prendre("38-admin-plan-de-table");

  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await prendre("39-le-mur", { attente: 1600, pageEntiere: false });

  // Période « Après » : le dernier visage de l'application.
  await base.query(
    `update public.parametres
        set periode_forcee = 'apres', periode_forcee_jusqu_a = now() + interval '1 hour'
      where id = 1`,
  );
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await prendre("40-merci");
  await page.goto(`${BASE}/mes-donnees`, { waitUntil: "networkidle" });
  await prendre("41-mes-donnees");
  await page.goto(`${BASE}/messages`, { waitUntil: "networkidle" });
  await prendre("42-livre-d-or");

  /**
   * Les écrans du jour J ne s'atteignent pas en attendant le 3 juin 2028 : on
   * pose une journée autour de l'instant présent et on force la période, le
   * temps de deux captures. Le `finally` remet tout comme avant.
   */
  await poserJourneeEtPeriode("03", "semaine");
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await prendre("31-semaine-j");
  await poserJourneeEtPeriode("03", "jour");
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await prendre("32-maintenant");
  await poserJourneeEtPeriode("02", "jour");
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await prendre("33-ceremonie-debranchee");

  await page.goto(new URL("../secours/index.html", import.meta.url).href, { waitUntil: "load" });
  await prendre("17-page-de-secours");

  await navigateur.close();
} finally {
  serveur.kill("SIGTERM");
  await base.query("delete from public.households where id = $1", [foyerId]);
  await base.query("delete from public.admin_users where email = $1", [emailAdmin]);
  // La base de développement retrouve son état : ni période forcée, ni
  // horaires simulés.
  await base.query(
    `update public.parametres set periode_forcee = null, periode_forcee_jusqu_a = null where id = 1`,
  );
  await base.query("update public.moments set starts_at = null, ends_at = null");
  await base.query("delete from public.seating_tables where label = 'Table des vignes'");
  await base.end();
  rmSync(MEDIAS, { recursive: true, force: true });
}
