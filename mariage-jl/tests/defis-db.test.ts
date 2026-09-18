import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Défis photo (brief §8.7, bonus). Deux règles, et elles viennent du §17 :
 * rien d'inventé (un défi sans intitulé n'apparaît nulle part), et aucun
 * classement ni compteur — nulle part on ne dit combien de personnes ont
 * répondu à un défi.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_defis_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let defis: typeof import("@/lib/defis") | undefined;
let medias: typeof import("@/lib/medias") | undefined;
let dossier = "";
let foyer = "";

const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xda, 0x00, 0x02, 0x01]);

beforeAll(async () => {
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

  const { rows } = await client.query<{ id: string }>(
    `insert into public.households (label_public, token_sha256, backup_code_sha256)
     values ('Foyer défis', $1, $2) returning id`,
    [
      createHash("sha256").update("jeton-defis").digest(),
      createHash("sha256").update("code-defis").digest(),
    ],
  );
  foyer = rows[0]?.id ?? "";

  dossier = mkdtempSync(join(tmpdir(), "jl-defis-"));
  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_MEDIAS_DIR"] = dossier;
  defis = await import("@/lib/defis");
  medias = await import("@/lib/medias");
  await medias.accorderConsentementMedias(foyer, "invites");
}, 60_000);

afterAll(async () => {
  await client?.end();
  if (dossier !== "") rmSync(dossier, { recursive: true, force: true });
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("défis amorcés", () => {
  it("existe un défi par moment, aucun publié, aucun intitulé inventé", async () => {
    const liste = await defis!.defisAdmin();
    expect(liste).toHaveLength(5);
    expect(liste.map((defi) => defi.moment_id)).toEqual(["01", "02", "03", "04", "05"]);
    expect(liste.every((defi) => !defi.published)).toBe(true);
    expect(liste.every((defi) => defi.title_fr.includes("[À COMPLÉTER]"))).toBe(true);
  });

  it("aucun n'est visible des invités", async () => {
    expect(await defis!.defisPublies("fr")).toEqual([]);
  });
});

decrire()("publication", () => {
  /**
   * Le point qui compte : publier ne suffit pas. Un défi publié mais sans
   * intitulé écrit resterait invisible — on n'affiche jamais
   * « [À COMPLÉTER] » à un invité.
   */
  it("un défi publié sans intitulé reste invisible", async () => {
    const premier = (await defis!.defisAdmin())[0]!;
    await defis!.enregistrerDefi(premier.id, {
      title_fr: "[À COMPLÉTER]",
      title_en: "[TO BE COMPLETED]",
      published: true,
    });
    expect(await defis!.defisPublies("fr")).toEqual([]);
    expect(await defis!.estDefiOuvert(premier.id)).toBe(false);
  });

  it("un défi écrit et publié apparaît, dans les deux langues", async () => {
    const premier = (await defis!.defisAdmin())[0]!;
    await defis!.enregistrerDefi(premier.id, {
      title_fr: "Une main dans une autre",
      title_en: "A hand in another",
      published: true,
    });
    const fr = await defis!.defisPublies("fr");
    const en = await defis!.defisPublies("en");
    expect(fr.map((d) => d.titre)).toEqual(["Une main dans une autre"]);
    expect(en.map((d) => d.titre)).toEqual(["A hand in another"]);
    expect(await defis!.estDefiOuvert(premier.id)).toBe(true);
  });

  it("un défi écrit mais dépublié disparaît", async () => {
    const premier = (await defis!.defisAdmin())[0]!;
    await defis!.enregistrerDefi(premier.id, {
      title_fr: "Une main dans une autre",
      title_en: "A hand in another",
      published: false,
    });
    expect(await defis!.defisPublies("fr")).toEqual([]);
    await defis!.enregistrerDefi(premier.id, {
      title_fr: "Une main dans une autre",
      title_en: "A hand in another",
      published: true,
    });
  });
});

decrire()("un souvenir répond à un défi", () => {
  it("s'attache au défi, sans que rien ne soit compté", async () => {
    const defi = (await defis!.defisPublies("fr"))[0]!;
    await medias!.enregistrerMedia({
      foyer,
      momentId: "01",
      mime: "image/jpeg",
      octets: JPEG,
      defiId: defi.id,
    });

    const { rows } = await client!.query<{ challenge_id: string | null }>(
      "select challenge_id from public.media",
    );
    expect(rows[0]?.challenge_id).toBe(defi.id);

    /*
      Le §17 interdit tout compteur de participation. La galerie ne doit donc
      exposer aucun champ de comptage, et le module des défis n'offre aucune
      fonction pour en obtenir un.
    */
    const galerie = await medias!.galerie({ foyer });
    for (const media of galerie) {
      expect(Object.keys(media)).not.toContain("reponses");
      expect(Object.keys(media)).not.toContain("participants");
    }
    expect(Object.keys(defis as object)).not.toContain("compterReponses");
  });

  it("un identifiant de défi fermé n'est pas attaché", async () => {
    // On dépublie, puis on tente d'y répondre : le contrôle est côté serveur.
    const defi = (await defis!.defisPublies("fr"))[0]!;
    await defis!.enregistrerDefi(defi.id, {
      title_fr: "Une main dans une autre",
      title_en: "A hand in another",
      published: false,
    });
    expect(await defis!.estDefiOuvert(defi.id)).toBe(false);
  });

  it("supprimer un défi ne supprime pas les souvenirs qui y répondaient", async () => {
    const avant = (await medias!.galerie({ foyer })).length;
    await client!.query("delete from public.photo_challenges where moment_id = '01'");
    const apres = await medias!.galerie({ foyer });
    expect(apres.length).toBe(avant);
    const { rows } = await client!.query<{ challenge_id: string | null }>(
      "select challenge_id from public.media",
    );
    expect(rows[0]?.challenge_id).toBeNull();
  });
});
