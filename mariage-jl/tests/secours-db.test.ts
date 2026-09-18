import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Page de secours (brief §0 bis et §10, plan B).
 *
 * Ce qui compte : elle dit **la même chose que l'application**, parce
 * qu'elle est régénérée depuis la base. Une page de secours qui affiche
 * « [À COMPLÉTER] » le jour où elle doit servir ne sert à rien.
 *
 * Et l'inverse compte autant : sans base, elle ne devine rien.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_secours_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;
const SORTIE = join(RACINE, "secours", "index.html");

let client: Client | undefined;
let indisponible: string | undefined;
let original = "";

/** Régénère la page, avec ou sans base, et renvoie son contenu. */
function composer(avecBase: boolean): string {
  execFileSync("node", [join(RACINE, "scripts", "build-secours.mjs")], {
    cwd: RACINE,
    env: avecBase
      ? { ...process.env, JL_DATABASE_URL: URL_BASE }
      : { ...process.env, JL_DATABASE_URL: undefined },
    stdio: "pipe",
  });
  return readFileSync(SORTIE, "utf8");
}

beforeAll(async () => {
  original = readFileSync(SORTIE, "utf8");
  const gestion = new Client({ connectionString: URL_ADMIN });
  try {
    await gestion.connect();
  } catch (erreur) {
    indisponible = `PostgreSQL injoignable : ${(erreur as Error).message}`;
    if (process.env["JL_REQUIRE_DB"] === "1") throw new Error(indisponible);
    return;
  }
  await gestion.query(`drop database if exists ${BASE}`);
  await gestion.query(`create database ${BASE}`);
  await gestion.end();

  client = new Client({ connectionString: URL_BASE });
  await client.connect();
  for (const fichier of [
    join(RACINE, "supabase", "tests", "00_compat_local.sql"),
    ...readdirSync(join(RACINE, "supabase", "migrations"))
      .filter((f) => f.endsWith(".sql"))
      .sort()
      .map((f) => join(RACINE, "supabase", "migrations", f)),
  ]) {
    await client.query(readFileSync(fichier, "utf8"));
  }
}, 60_000);

afterAll(async () => {
  await client?.end();
  // La page du dépôt est remise telle qu'elle était : un test ne laisse pas
  // de trace dans les fichiers livrés.
  if (original !== "") writeFileSync(SORTIE, original);
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("sans contenu écrit", () => {
  it("garde les mentions d'attente plutôt que d'inventer", async () => {
    const page = composer(true);
    expect(page).toContain("[À COMPLÉTER]");
    // Les cinq moments y sont quand même, avec leurs couleurs officielles.
    for (const [id, couleur] of [
      ["01", "#E9B131"],
      ["02", "#365D87"],
      ["03", "#CB5726"],
      ["04", "#721F23"],
      ["05", "#84568D"],
    ]) {
      expect(page, id).toContain(couleur);
    }
    expect(page).toContain("L’Éclat");
    expect(page).toContain("La Nuit");
    // Aucun lien d'appel mort.
    expect(page).not.toContain('href="tel:"');
  });

  it("se compose aussi sans base du tout", () => {
    const page = composer(false);
    expect(page).toContain("[À COMPLÉTER]");
    expect(page).toContain("Domaine de Roiffé");
    expect(page).toContain("<svg");
  });
});

decrire()("avec le contenu écrit dans l'admin", () => {
  it("dit la même chose que l'application", async () => {
    await client!.query(
      `update public.moments
          set starts_at = (date '2028-06-03' + time '15:30') at time zone 'Europe/Paris',
              ends_at   = (date '2028-06-03' + time '16:15') at time zone 'Europe/Paris',
              place = 'La chapelle du domaine'
        where id = '02'`,
    );
    await client!.query(
      `update public.content_blocks
          set value = jsonb_build_object('texte', 'Par la D147, puis l’allée de tilleuls.')
        where key = 'infos.venir' and locale = 'fr'`,
    );
    await client!.query(
      `update public.content_blocks
          set value = jsonb_build_object('texte', 'Camille', 'telephone', '+33 6 12 34 56 78')
        where key = 'aide.regie' and locale = 'fr'`,
    );
    await client!.query(
      `update public.content_blocks
          set value = jsonb_build_object('texte', 'JL-invites / motdepasse', 'lien', null)
        where key = 'jour.wifi' and locale = 'fr'`,
    );
    await client!.query(
      "update public.parametres set date_limite_reponse = date '2028-04-15'",
    );

    const page = composer(true);
    expect(page).toContain("de 15:30 à 16:15");
    expect(page).toContain("La chapelle du domaine");
    expect(page).toContain("Par la D147, puis l’allée de tilleuls.");
    expect(page).toContain("15/04/2028");
    // Le numéro devient un lien composable, débarrassé de ses espaces.
    expect(page).toContain('href="tel:+33612345678"');
    expect(page).toContain("JL-invites / motdepasse");
  });

  /**
   * La page est servie telle quelle, sans script : un texte saisi dans
   * l'admin doit y arriver échappé, sinon une balise collée par erreur
   * casserait la seule page qui doit tenir quand tout tombe.
   */
  it("échappe ce qui vient de la saisie", async () => {
    await client!.query(
      `update public.content_blocks
          set value = jsonb_build_object('texte', '<script>alert(1)</script> & "guillemets"')
        where key = 'infos.venir' and locale = 'fr'`,
    );
    const page = composer(true);
    expect(page).not.toContain("<script>alert(1)</script>");
    expect(page).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(page).toContain("&amp;");
  });

  it("reste autonome : aucun script, aucune police distante", () => {
    const page = composer(true);
    expect(page).not.toMatch(/<script/i);
    expect(page).not.toContain("fonts.googleapis.com");
    expect(page).not.toContain("http://");
  });
});
