import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Régie du jour J contre un vrai PostgreSQL. Ce qui est vérifié ici, c'est ce
 * qui se verra de tous les invités en même temps : un décalage entraîne les
 * moments suivants, la cérémonie coupe les envois toute seule et les rouvre
 * toute seule, et la régie n'a accès à rien d'autre.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_regie_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let regie: typeof import("@/lib/regie") | undefined;
let journee: typeof import("@/lib/journee") | undefined;
let contenus: typeof import("@/lib/contenus-admin") | undefined;

const JOUR = "2028-06-03";

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

  process.env["JL_DATABASE_URL"] = URL_BASE;
  regie = await import("@/lib/regie");
  journee = await import("@/lib/journee");
  contenus = await import("@/lib/contenus-admin");

  // Une journée complète, saisie comme les mariés la saisiraient.
  const horaires: ReadonlyArray<[string, string, string]> = [
    ["01", "12:00", "14:00"],
    ["02", "14:00", "15:00"],
    ["03", "15:00", "18:00"],
    ["04", "18:00", "21:00"],
    ["05", "21:00", "23:59"],
  ];
  for (const [id, debut, fin] of horaires) {
    await contenus.enregistrerMoment(id, {
      debut,
      fin,
      place: null,
      ambience_fr: null,
      ambience_en: null,
      detail_fr: null,
      detail_en: null,
    });
  }
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

/** Instant absolu correspondant à une heure locale du domaine. */
const aParis = async (heure: string): Promise<Date> => {
  const { rows } = await client!.query<{ t: Date }>(
    `select (date '${JOUR}' + time '${heure}') at time zone 'Europe/Paris' as t`,
  );
  return rows[0]!.t;
};

decrire()("décalage d'un moment", () => {
  it("entraîne les moments suivants, et seulement eux", async () => {
    const touches = await regie!.decalerDepuis("03", 20);
    expect(touches).toBe(3); // 03, 04, 05

    const { rows } = await client!.query<{ id: string; shift_minutes: number }>(
      "select id, shift_minutes from public.moments order by id",
    );
    expect(rows.map((r) => r.shift_minutes)).toEqual([0, 0, 20, 20, 20]);
  });

  it("déplace réellement l'heure vue par l'invité", async () => {
    const { moments, heure } = await import("@/lib/moments");
    const liste = await moments();
    expect(heure(liste.find((m) => m.id === "03")?.starts_at ?? null, "fr")).toBe("15:20");
    // Le moment d'avant n'a pas bougé.
    expect(heure(liste.find((m) => m.id === "02")?.starts_at ?? null, "fr")).toBe("14:00");
  });

  it("s'accumule quand la journée glisse deux fois", async () => {
    await regie!.decalerDepuis("03", 10);
    const { rows } = await client!.query<{ shift_minutes: number }>(
      "select shift_minutes from public.moments where id = '03'",
    );
    expect(rows[0]?.shift_minutes).toBe(30);
  });

  it("revient d'un geste aux horaires prévus", async () => {
    await regie!.annulerDecalages();
    const { rows } = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.moments where shift_minutes <> 0",
    );
    expect(Number(rows[0]?.n)).toBe(0);
  });
});

decrire()("état de la journée", () => {
  it("désigne le moment en cours à l'heure du domaine", async () => {
    const etat = await journee!.etatJournee(await aParis("15:30"));
    expect(etat.courant?.id).toBe("03");
    expect(etat.suivant?.id).toBe("04");
    expect(etat.horairesConnus).toBe(true);
  });

  /**
   * Le cœur de la cérémonie débranchée : la coupure des envois s'active et se
   * lève **sans aucun geste**, sur la seule base de l'heure.
   */
  it("coupe les envois pendant la cérémonie, et les rouvre à la fin", async () => {
    const pendant = await journee!.etatJournee(await aParis("14:30"));
    expect(pendant.pendantCeremonie).toBe(true);
    expect(pendant.envoisEnPause).toBe(true);

    const apres = await journee!.etatJournee(await aParis("15:30"));
    expect(apres.pendantCeremonie).toBe(false);
    expect(apres.envoisEnPause).toBe(false);
  });

  it("ne coupe rien si les mariés ont désactivé le réglage", async () => {
    await regie!.reglerCeremonieDebranchee(false);
    const pendant = await journee!.etatJournee(await aParis("14:30"));
    expect(pendant.pendantCeremonie).toBe(false);
    expect(pendant.envoisEnPause).toBe(false);
    await regie!.reglerCeremonieDebranchee(true);
  });

  it("la coupure posée par la régie tient hors de la cérémonie", async () => {
    await regie!.couperEnvois(true);
    const etat = await journee!.etatJournee(await aParis("19:00"));
    expect(etat.pauseManuelle).toBe(true);
    expect(etat.envoisEnPause).toBe(true);
    expect(etat.pendantCeremonie).toBe(false);

    await regie!.couperEnvois(false);
    expect((await journee!.etatJournee(await aParis("19:00"))).envoisEnPause).toBe(false);
  });
});

decrire()("contacts de l'écran Aide", () => {
  it("n'expose pas de bouton d'appel tant que le numéro n'est pas écrit", async () => {
    const { contacts } = await import("@/lib/contenus");
    const avant = await contacts("fr");
    expect(avant).toHaveLength(2);
    expect(avant.every((contact) => contact.telephone === null)).toBe(true);
  });

  it("enregistre le numéro une fois pour les deux langues", async () => {
    await contenus!.enregistrerContact(
      "aide.regie",
      { texte_fr: "Camille, l’équipe du jour", texte_en: "Camille, the team", telephone: "+33 6 12 34 56 78" },
      "maries@exemple.test",
    );
    const { contacts } = await import("@/lib/contenus");
    const fr = (await contacts("fr")).find((c) => c.cle === "aide.regie");
    const en = (await contacts("en")).find((c) => c.cle === "aide.regie");
    expect(fr?.nom).toBe("Camille, l’équipe du jour");
    expect(en?.nom).toBe("Camille, the team");
    expect(en?.telephone).toBe("+33 6 12 34 56 78");
  });

  it("refuse ce qui ne peut pas se composer", () => {
    for (const bon of ["+33612345678", "+33 6 12 34 56 78", "06.12.34.56.78", "0612345678"]) {
      expect(contenus!.telephoneAcceptable(bon), bon).toBe(true);
    }
    for (const mauvais of ["tel:0612345678", "javascript:alert(1)", "appelez-moi", "12345", ""]) {
      expect(contenus!.telephoneAcceptable(mauvais), mauvais).toBe(false);
    }
    expect(contenus!.numeroComposable("+33 6 12 34 56 78")).toBe("+33612345678");
  });
});

decrire()("journal d'audit de la régie", () => {
  it("garde la trace des gestes, sans adresse", async () => {
    const { rows } = await client!.query<{ action: string; role: string; target: string }>(
      "select action, role, target from public.audit_log order by id",
    );
    const actions = rows.map((r) => r.action);
    expect(actions).toContain("regie.decalage");
    expect(actions).toContain("regie.envois");
    for (const ligne of rows) expect(ligne.target).not.toContain("@");
  });
});
