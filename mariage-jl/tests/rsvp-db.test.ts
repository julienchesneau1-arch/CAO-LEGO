import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Réponse des invités : le vrai code (lib/rsvp.ts) contre un vrai PostgreSQL.
 * On vérifie ce qui compte : l'enregistrement en un tap, le verrou après la
 * date limite, la transaction complète, le cloisonnement entre foyers et la
 * règle de consentement des allergies (donnée de santé, brief §11).
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_rsvp_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let rsvp: typeof import("@/lib/rsvp") | undefined;

let foyer = "";
let foyerVoisin = "";
let invite = "";
let inviteVoisin = "";
const MOMENTS = ["01", "02", "03", "04", "05"];

const empreinte = (s: string): Buffer => createHash("sha256").update(s, "utf8").digest();

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

  const poser = async (label: string, prenom: string): Promise<[string, string]> => {
    const { rows } = await client!.query<{ id: string }>(
      `insert into public.households (label_public, token_sha256, backup_code_sha256)
       values ($1, $2, $3) returning id`,
      [label, empreinte(`jeton-${label}`), empreinte(`code-${label}`)],
    );
    const maison = rows[0]?.id ?? "";
    const { rows: invites } = await client!.query<{ id: string }>(
      `insert into public.guests (household_id, first_name) values ($1, $2) returning id`,
      [maison, prenom],
    );
    return [maison, invites[0]?.id ?? ""];
  };

  [foyer, invite] = await poser("Foyer testé", "Camille");
  [foyerVoisin, inviteVoisin] = await poser("Foyer voisin", "Dominique");

  process.env["JL_DATABASE_URL"] = URL_BASE;
  rsvp = await import("@/lib/rsvp");
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

const details = (surcharges: Partial<Parameters<NonNullable<typeof rsvp>["enregistrerDetails"]>[1]> = {}) => ({
  presences: { [invite]: MOMENTS },
  menus: { [invite]: "" },
  regimes: { [invite]: [] },
  allergies: { [invite]: "" },
  consentementAllergies: false,
  versionConsentement: "test-v1",
  ...surcharges,
});

decrire()("étape 1 : un tap", () => {
  it("enregistre le oui immédiatement", async () => {
    await rsvp!.enregistrerStatut(foyer, "yes");
    expect((await rsvp!.reponseDuFoyer(foyer))?.statut).toBe("yes");
  });

  it("accepte un changement d'avis", async () => {
    await rsvp!.enregistrerStatut(foyer, "maybe");
    expect((await rsvp!.reponseDuFoyer(foyer))?.statut).toBe("maybe");
    await rsvp!.enregistrerStatut(foyer, "yes");
  });

  it("refuse de toucher une réponse verrouillée", async () => {
    await client!.query("update public.rsvp set locked_at = now() where household_id = $1", [foyer]);
    await rsvp!.enregistrerStatut(foyer, "no");
    expect((await rsvp!.reponseDuFoyer(foyer))?.statut).toBe("yes");
    await client!.query("update public.rsvp set locked_at = null where household_id = $1", [foyer]);
  });

  it("se verrouille tout seul passé la date limite", async () => {
    expect(await rsvp!.reponseVerrouillee()).toBe(false);
    await client!.query(
      "update public.parametres set date_limite_reponse = current_date - 1 where id = 1",
    );
    expect(await rsvp!.reponseVerrouillee()).toBe(true);
    await client!.query("update public.parametres set date_limite_reponse = null where id = 1");
  });
});

decrire()("étapes 2 à 4 : une transaction", () => {
  it("coche les cinq moments par défaut", async () => {
    await rsvp!.enregistrerDetails(foyer, details(), MOMENTS);
    const lignes = await client!.query<{ moment_id: string; attending: boolean }>(
      "select moment_id, attending from public.rsvp_attendance where guest_id = $1 order by moment_id",
      [invite],
    );
    expect(lignes.rows.filter((l) => l.attending).map((l) => l.moment_id)).toEqual(MOMENTS);
  });

  it("enregistre une absence à un seul moment", async () => {
    await rsvp!.enregistrerDetails(foyer, details({ presences: { [invite]: ["01", "02"] } }), MOMENTS);
    const lignes = await client!.query<{ moment_id: string }>(
      "select moment_id from public.rsvp_attendance where guest_id = $1 and attending order by moment_id",
      [invite],
    );
    expect(lignes.rows.map((l) => l.moment_id)).toEqual(["01", "02"]);
  });

  it("garde menus et régimes", async () => {
    await rsvp!.enregistrerDetails(
      foyer,
      details({ menus: { [invite]: "Poisson" }, regimes: { [invite]: ["sans_alcool"] } }),
      MOMENTS,
    );
    const invites = await rsvp!.invitesDuFoyer(foyer);
    expect(invites[0]?.menu_choice).toBe("Poisson");
    expect(invites[0]?.diet_flags).toEqual(["sans_alcool"]);
  });

  it("ne touche jamais l'invité d'un autre foyer", async () => {
    await rsvp!.enregistrerStatut(foyerVoisin, "yes");
    await rsvp!.enregistrerDetails(
      foyer,
      details({
        presences: { [inviteVoisin]: ["01"] },
        menus: { [inviteVoisin]: "Intrusion" },
        regimes: { [inviteVoisin]: [] },
        allergies: { [inviteVoisin]: "" },
      }),
      MOMENTS,
    );
    const voisin = await rsvp!.invitesDuFoyer(foyerVoisin);
    expect(voisin[0]?.menu_choice).toBeNull();
    expect(voisin[0]?.presences).toEqual([]);
  });
});

decrire()("allergies : donnée de santé", () => {
  it("n'enregistre rien sans consentement explicite", async () => {
    await rsvp!.enregistrerDetails(
      foyer,
      details({ allergies: { [invite]: "arachides" }, consentementAllergies: false }),
      MOMENTS,
    );
    const lignes = await client!.query("select * from public.health_allergies where guest_id = $1", [
      invite,
    ]);
    expect(lignes.rowCount).toBe(0);
  });

  it("enregistre avec consentement, en datant le consentement et la purge", async () => {
    await rsvp!.enregistrerDetails(
      foyer,
      details({ allergies: { [invite]: "arachides" }, consentementAllergies: true }),
      MOMENTS,
    );
    const ligne = await client!.query<{
      content: string;
      consent_text_version: string;
      purge_after: Date;
    }>(
      "select content, consent_text_version, purge_after from public.health_allergies where guest_id = $1",
      [invite],
    );
    expect(ligne.rows[0]?.content).toBe("arachides");
    expect(ligne.rows[0]?.consent_text_version).toBe("test-v1");
    // 30 jours après le mariage (3 juin 2028).
    expect(ligne.rows[0]?.purge_after.toISOString().slice(0, 10)).toBe("2028-07-03");
  });

  it("efface la donnée si le consentement est retiré", async () => {
    await rsvp!.enregistrerDetails(
      foyer,
      details({ allergies: { [invite]: "arachides" }, consentementAllergies: false }),
      MOMENTS,
    );
    const lignes = await client!.query("select * from public.health_allergies where guest_id = $1", [
      invite,
    ]);
    expect(lignes.rowCount).toBe(0);
  });

  it("efface la donnée si le champ est vidé, même avec consentement", async () => {
    await rsvp!.enregistrerDetails(
      foyer,
      details({ allergies: { [invite]: "arachides" }, consentementAllergies: true }),
      MOMENTS,
    );
    await rsvp!.enregistrerDetails(
      foyer,
      details({ allergies: { [invite]: "  " }, consentementAllergies: true }),
      MOMENTS,
    );
    const lignes = await client!.query("select * from public.health_allergies where guest_id = $1", [
      invite,
    ]);
    expect(lignes.rowCount).toBe(0);
  });
});

decrire()("validation", () => {
  it("refuse un régime inconnu", () => {
    // Valeur volontairement hors liste : c'est zod qui doit la refuser,
    // pas seulement TypeScript (un formulaire peut envoyer n'importe quoi).
    const resultat = rsvp!.SchemaDetails.safeParse({
      ...details(),
      regimes: { [invite]: ["sans_gluten"] },
    });
    expect(resultat.success).toBe(false);
  });

  it("refuse un message démesuré", () => {
    const resultat = rsvp!.SchemaDetails.safeParse({
      ...details(),
      message: "x".repeat(2_001),
    });
    expect(resultat.success).toBe(false);
  });
});
