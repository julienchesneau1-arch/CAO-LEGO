import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { PDFDocument } from "pdf-lib";
import { Client } from "pg";

/**
 * Plan de table contre un vrai PostgreSQL. Ce qui compte : la recherche
 * trouve un prénom accentué tapé sans accent, et elle ne révèle **que** le
 * prénom et la table — jamais le foyer, la réponse ou le régime (§11).
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_table_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let table: typeof import("@/lib/table") | undefined;
let imprimables: typeof import("@/lib/imprimables") | undefined;
let foyer = "";
const invites: Record<string, string> = {};

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
     values ('Famille Essai', $1, $2) returning id`,
    [
      createHash("sha256").update("jeton-table").digest(),
      createHash("sha256").update("code-table").digest(),
    ],
  );
  foyer = rows[0]?.id ?? "";

  for (const [index, prenom] of ["Chloé", "Joël", "Camille", "Élodie"].entries()) {
    const ligne = await client.query<{ id: string }>(
      `insert into public.guests (household_id, first_name, sort_order)
       values ($1, $2, $3) returning id`,
      [foyer, prenom, index],
    );
    invites[prenom] = ligne.rows[0]?.id ?? "";
  }

  process.env["JL_DATABASE_URL"] = URL_BASE;
  table = await import("@/lib/table");
  imprimables = await import("@/lib/imprimables");
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("tables et affectations", () => {
  it("n'affiche rien tant qu'aucune table n'existe", async () => {
    expect(await table!.tables()).toEqual([]);
    const places = await table!.placesDuFoyer(foyer);
    expect(places).toHaveLength(4);
    expect(places.every((place) => place.table_id === null)).toBe(true);
  });

  it("crée une table, y pose des personnes, et les relit", async () => {
    const une = await table!.creerTable("Table 1", 8, 1);
    const deux = await table!.creerTable("Table 2", 8, 2);
    expect(une).toBeTypeOf("string");

    await table!.affecter(invites["Chloé"] as string, une as string);
    await table!.affecter(invites["Joël"] as string, une as string);
    await table!.affecter(invites["Camille"] as string, deux as string);

    expect(await table!.prenomsDeLaTable(une as string)).toEqual(["Chloé", "Joël"]);
    const places = await table!.placesDuFoyer(foyer);
    expect(places.find((p) => p.prenom === "Chloé")?.table_label).toBe("Table 1");
    expect(places.find((p) => p.prenom === "Élodie")?.table_label).toBeNull();
  });

  it("déplacer quelqu'un ne crée pas de doublon", async () => {
    const [, deux] = await table!.tables();
    await table!.affecter(invites["Chloé"] as string, deux!.id);
    const { rows } = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.seating_assign where guest_id = $1",
      [invites["Chloé"]],
    );
    expect(Number(rows[0]?.n)).toBe(1);
    const [une] = await table!.tables();
    await table!.affecter(invites["Chloé"] as string, une!.id);
  });

  it("retirer quelqu'un d'une table le laisse sans table, pas sans invitation", async () => {
    await table!.affecter(invites["Camille"] as string, null);
    const places = await table!.placesDuFoyer(foyer);
    expect(places.find((p) => p.prenom === "Camille")?.table_id).toBeNull();
    expect(places).toHaveLength(4);
    const [, deux] = await table!.tables();
    await table!.affecter(invites["Camille"] as string, deux!.id);
  });

  it("supprimer une table libère ses convives", async () => {
    const [, deux] = await table!.tables();
    await table!.supprimerTable(deux!.id);
    const places = await table!.placesDuFoyer(foyer);
    expect(places.find((p) => p.prenom === "Camille")?.table_id).toBeNull();
    expect(await table!.tables()).toHaveLength(1);
  });
});

decrire()("recherche d'une place", () => {
  it("trouve un prénom accentué tapé sans accent", async () => {
    expect((await table!.chercherUnePlace("chloe")).map((r) => r.prenom)).toEqual(["Chloé"]);
    expect((await table!.chercherUnePlace("JOEL")).map((r) => r.prenom)).toEqual(["Joël"]);
    expect((await table!.chercherUnePlace("elodie")).map((r) => r.prenom)).toEqual(["Élodie"]);
  });

  it("trouve aussi avec les accents, et au milieu du prénom", async () => {
    expect((await table!.chercherUnePlace("Chloé")).map((r) => r.prenom)).toEqual(["Chloé"]);
    expect((await table!.chercherUnePlace("mill")).map((r) => r.prenom)).toEqual(["Camille"]);
  });

  it("demande deux lettres : une seule renverrait presque tout le monde", async () => {
    expect(await table!.chercherUnePlace("c")).toEqual([]);
    expect(await table!.chercherUnePlace(" ")).toEqual([]);
  });

  it("dit « pas encore placé » sans mentir sur une table inexistante", async () => {
    const trouve = await table!.chercherUnePlace("elodie");
    expect(trouve[0]?.table).toBeNull();
  });

  /**
   * Le point de confidentialité : chercher quelqu'un donne son prénom et sa
   * table, rien de plus. Pas de foyer, pas de réponse, pas de régime.
   */
  it("ne renvoie que le prénom et la table", async () => {
    const trouve = await table!.chercherUnePlace("chloe");
    expect(Object.keys(trouve[0] ?? {}).sort()).toEqual(["prenom", "table"]);
  });
});

decrire()("imprimables", () => {
  /**
   * On compte les pages en relisant le PDF avec pdf-lib plutôt qu'en
   * cherchant « /Type /Page » dans les octets : pdf-lib compresse les
   * objets, et un test bâti sur le texte brut passerait ou échouerait selon
   * la version de la bibliothèque, sans rien dire du document.
   */
  const pages = async (pdf: Uint8Array): Promise<number> =>
    (await PDFDocument.load(pdf)).getPageCount();

  const MOMENTS = [
    { id: "01", nom: "L’Éclat", heure: "12:00", lieu: "La cour" },
    { id: "02", nom: "L’Horizon", heure: null, lieu: null },
  ] as const;

  it("produit un PDF de cartes de table, une page par table", async () => {
    const pdf = await imprimables!.cartesDeTablePdf(
      [
        { table: "Table 1", prenoms: ["Chloé", "Joël"] },
        { table: "Table 2", prenoms: ["Camille"] },
      ],
      {
        domaine: "exemple.test",
        moments: [...MOMENTS],
        wifi: "JL-invites / motdepasse",
        contact: { role: "L’équipe du jour", nom: "Camille", telephone: "+33612345678" },
        libelles: {
          signature: "J&L — DEPUIS 2018",
          programme: "LE PROGRAMME",
          heure_inconnue: "horaire à confirmer",
          wifi: "Wi-Fi :",
        },
      },
    );
    expect(Buffer.from(pdf).toString("latin1").startsWith("%PDF")).toBe(true);
    // Deux tables, donc deux pages.
    expect(await pages(pdf)).toBe(2);
    expect(pdf.byteLength).toBeGreaterThan(2000);
  });

  it("imprime une carte générique même sans aucune table", async () => {
    const pdf = await imprimables!.cartesDeTablePdf([], {
      domaine: "",
      moments: [...MOMENTS],
      wifi: null,
      contact: null,
      libelles: { signature: "J&L", programme: "LE PROGRAMME", heure_inconnue: "?", wifi: "Wi-Fi :" },
    });
    expect(await pages(pdf)).toBe(1);
  });

  it("produit une fiche régie d'une seule page", async () => {
    const pdf = await imprimables!.ficheRegiePdf(
      {
        domaine: "exemple.test",
        moments: [...MOMENTS],
        contacts: [{ role: "L’équipe du jour", nom: "Camille", telephone: "+33612345678" }],
        wifi: "JL-invites / motdepasse",
        procedures: [{ titre: "Plus de réseau", texte: "Les cartes de table portent le programme." }],
      },
      {
        titre: "FICHE RÉGIE",
        horaires: "LES HORAIRES",
        contacts: "LES CONTACTS",
        sans_contact: "Aucun numéro",
        procedures: "SI QUELQUE CHOSE TOMBE",
        wifi: "Wi-Fi :",
        heure_inconnue: "horaire à confirmer",
      },
    );
    expect(Buffer.from(pdf).toString("latin1").startsWith("%PDF")).toBe(true);
    expect(await pages(pdf)).toBe(1);
  });

  it("ne tombe pas sur une fiche sans aucun contact écrit", async () => {
    await expect(
      imprimables!.ficheRegiePdf(
        { domaine: "", moments: [], contacts: [], wifi: null, procedures: [] },
        {
          titre: "FICHE",
          horaires: "HORAIRES",
          contacts: "CONTACTS",
          sans_contact: "Aucun numéro écrit.",
          procedures: "PANNES",
          wifi: "Wi-Fi :",
          heure_inconnue: "?",
        },
      ),
    ).resolves.toBeInstanceOf(Uint8Array);
  });
});
