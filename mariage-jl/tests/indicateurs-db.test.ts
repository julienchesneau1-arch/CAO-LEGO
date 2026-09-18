import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "pg";
import { atteint, pourcentage, type Indicateur } from "@/lib/indicateurs";

/**
 * Indicateurs de réussite (brief §16), **sans traceur**.
 *
 * Ce qui est vérifié ici tient en une phrase : ce qu'on ne peut pas mesurer
 * sans tracer est renvoyé `undefined`, jamais approché — et ce qu'on mesure
 * est juste, y compris au bord (base vide, foyer qui répond sans que son
 * ouverture ait été enregistrée).
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_indicateurs_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let module: typeof import("@/lib/indicateurs") | undefined;
let medias: typeof import("@/lib/medias") | undefined;
let dossier = "";

const foyers: string[] = [];

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

  dossier = mkdtempSync(join(tmpdir(), "jl-indic-"));
  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_MEDIAS_DIR"] = dossier;
  module = await import("@/lib/indicateurs");
  medias = await import("@/lib/medias");
}, 60_000);

afterAll(async () => {
  await client?.end();
  if (dossier !== "") rmSync(dossier, { recursive: true, force: true });
});

const decrire = () => (indisponible ? describe.skip : describe);

const trouver = (liste: ReadonlyArray<Indicateur>, cle: string): Indicateur =>
  liste.find((indicateur) => indicateur.cle === cle) as Indicateur;

async function creerFoyer(nom: string): Promise<string> {
  const { rows } = await client!.query<{ id: string }>(
    `insert into public.households (label_public, token_sha256, backup_code_sha256)
     values ($1, $2, $3) returning id`,
    [
      nom,
      createHash("sha256").update(nom).digest(),
      createHash("sha256").update(`${nom}-code`).digest(),
    ],
  );
  const id = rows[0]?.id ?? "";
  foyers.push(id);
  return id;
}

decrire()("sur une base vide", () => {
  /**
   * Le piège à éviter : afficher « 0 % — pas atteint » sur zéro foyer. Ce
   * serait un jugement porté sur rien.
   */
  it("ne prononce aucun verdict plutôt que d'en inventer un", async () => {
    const { liste, delaiMedianS } = await module!.indicateurs();
    expect(atteint(trouver(liste, "ouverts"))).toBeUndefined();
    expect(atteint(trouver(liste, "reponses"))).toBeUndefined();
    expect(delaiMedianS).toBeUndefined();
  });

  it("dit atteint, et non indisponible, pour un objectif de zéro", async () => {
    const { liste } = await module!.indicateurs();
    expect(atteint(trouver(liste, "emails_echoues"))).toBe(true);
  });
});

decrire()("ce qui se mesure", () => {
  it("compte les ouvertures et les réponses en proportion des foyers", async () => {
    const a = await creerFoyer("Foyer A");
    const b = await creerFoyer("Foyer B");
    await creerFoyer("Foyer C");

    await client!.query(
      "update public.households set first_opened_at = now() - interval '10 minutes' where id = any($1::uuid[])",
      [[a, b]],
    );
    await client!.query("insert into public.rsvp (household_id, status) values ($1, 'yes')", [a]);

    const { liste } = await module!.indicateurs();
    const ouverts = trouver(liste, "ouverts");
    expect(ouverts.valeur).toBe(2);
    expect(pourcentage(ouverts.valeur as number, ouverts.sur as number)).toBe(67);
    expect(atteint(ouverts)).toBe(false);

    const reponses = trouver(liste, "reponses");
    expect(reponses.valeur).toBe(1);
    expect(pourcentage(reponses.valeur as number, reponses.sur as number)).toBe(33);
  });

  /**
   * « Réponse en moins de 2 minutes » : la mesure porte sur le délai entre
   * la première ouverture et la réponse. Un foyer dont l'ouverture n'a pas
   * été enregistrée n'entre dans aucun des deux comptes — sinon il
   * fausserait la proportion, dans un sens comme dans l'autre.
   */
  it("mesure le délai ouverture → réponse, et écarte les foyers non mesurables", async () => {
    const rapide = await creerFoyer("Foyer rapide");
    await client!.query(
      "update public.households set first_opened_at = now() - interval '30 seconds' where id = $1",
      [rapide],
    );
    await client!.query("insert into public.rsvp (household_id, status) values ($1, 'yes')", [
      rapide,
    ]);

    // Un foyer qui a répondu sans ouverture enregistrée : hors mesure.
    const sansOuverture = await creerFoyer("Foyer sans ouverture");
    await client!.query("insert into public.rsvp (household_id, status) values ($1, 'no')", [
      sansOuverture,
    ]);

    const { liste, delaiMedianS } = await module!.indicateurs();
    const rapides = trouver(liste, "rapides");
    // Deux réponses mesurables : celle de « Foyer A » (10 min) et celle-ci.
    expect(rapides.sur).toBe(2);
    expect(rapides.valeur).toBe(1);
    expect(pourcentage(rapides.valeur as number, rapides.sur as number)).toBe(50);

    // La médiane porte sur les mêmes deux réponses.
    expect(delaiMedianS).toBeGreaterThan(30);
    expect(delaiMedianS).toBeLessThan(600);

    // La réponse du foyer sans ouverture est bien comptée dans « réponses ».
    expect(trouver(liste, "reponses").valeur).toBe(3);
  });

  it("compte les souvenirs publiés, et pas les masqués", async () => {
    const auteur = foyers[0] as string;
    await medias!.accorderConsentementMedias(auteur, "invites");
    const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xda, 0x00, 0x02, 0x01]);
    for (let index = 0; index < 3; index += 1) {
      await medias!.enregistrerMedia({
        foyer: auteur,
        momentId: "03",
        mime: "image/jpeg",
        octets: jpeg,
      });
    }
    expect(trouver((await module!.indicateurs()).liste, "souvenirs").valeur).toBe(3);

    const premier = (await medias!.galerie({ foyer: auteur }))[0];
    await medias!.masquer(premier!.id, true);
    expect(trouver((await module!.indicateurs()).liste, "souvenirs").valeur).toBe(2);
  });

  it("compte les e-mails définitivement échoués", async () => {
    await client!.query(
      `insert into public.emails (destinataire, sujet, corps, statut)
       values ('a@exemple.test', 's', 'c', 'echec')`,
    );
    const emails = trouver((await module!.indicateurs()).liste, "emails_echoues");
    expect(emails.valeur).toBe(1);
    expect(atteint(emails)).toBe(false);
  });
});

decrire()("ce qui ne se mesure pas sans traceur", () => {
  /**
   * Le cœur du §16 : « sans traceur ». Quatre indicateurs du brief ne sont
   * pas mesurables ainsi. Ils restent dans la liste, avec leur raison —
   * les cacher ferait croire qu'on les a oubliés, les approcher ferait
   * croire à un fait.
   */
  it("renvoie undefined et une raison, jamais une approximation", async () => {
    const { liste } = await module!.indicateurs();
    for (const cle of ["envois_echoues", "questions", "interventions", "incidents"]) {
      const indicateur = trouver(liste, cle);
      expect(indicateur.valeur, cle).toBeUndefined();
      expect(indicateur.pourquoi, cle).toBeTypeOf("string");
      expect(atteint(indicateur), cle).toBeUndefined();
    }
  });

  it("couvre exactement les neuf indicateurs du brief", async () => {
    const { liste } = await module!.indicateurs();
    expect(liste.map((i) => i.cle).sort()).toEqual(
      [
        "emails_echoues",
        "envois_echoues",
        "incidents",
        "interventions",
        "ouverts",
        "questions",
        "rapides",
        "reponses",
        "souvenirs",
      ].sort(),
    );
  });
});

describe("règles d'affichage", () => {
  it("ne divise jamais par zéro", () => {
    expect(pourcentage(0, 0)).toBeUndefined();
    expect(pourcentage(3, 0)).toBeUndefined();
    expect(pourcentage(1, 3)).toBe(33);
  });

  it("juge un objectif en nombre par « au moins », et un zéro par « exactement »", () => {
    const nombre = (valeur: number, objectif: number): Indicateur => ({
      cle: "x",
      valeur,
      sur: undefined,
      objectif,
      unite: "nombre",
    });
    expect(atteint(nombre(300, 300))).toBe(true);
    expect(atteint(nombre(299, 300))).toBe(false);
    expect(atteint(nombre(0, 0))).toBe(true);
    expect(atteint(nombre(1, 0))).toBe(false);
  });
});
