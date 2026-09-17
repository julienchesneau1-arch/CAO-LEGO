import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Annonces, rappels e-mail et file d'envoi : le vrai code contre un vrai
 * PostgreSQL. Ce qui est vérifié ici, c'est ce qui engage vis-à-vis des
 * invités : pas d'envoi sans consentement, désinscription en un seul usage,
 * et rien de perdu quand un envoi échoue.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_v2_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let annonces: typeof import("@/lib/annonces") | undefined;
let rappels: typeof import("@/lib/rappels") | undefined;
let email: typeof import("@/lib/email") | undefined;
let foyer = "";

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
     values ('Foyer V2', $1, $2) returning id`,
    [createHash("sha256").update("jeton-v2").digest(), createHash("sha256").update("code-v2").digest()],
  );
  foyer = rows[0]?.id ?? "";

  process.env["JL_DATABASE_URL"] = URL_BASE;
  annonces = await import("@/lib/annonces");
  rappels = await import("@/lib/rappels");
  email = await import("@/lib/email");
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("fil d'annonces", () => {
  it("publie et relit dans les deux langues, du plus récent au plus ancien", async () => {
    await annonces!.publierAnnonce("Première annonce.", "First announcement.", "admin");
    await annonces!.publierAnnonce("Deuxième annonce.", "Second announcement.", "admin");

    const fr = await annonces!.annonces("fr");
    const en = await annonces!.annonces("en");
    expect(fr[0]?.texte).toBe("Deuxième annonce.");
    expect(en[0]?.texte).toBe("Second announcement.");
    expect(fr).toHaveLength(2);
  });

  it("donne la dernière annonce pour l'accueil", async () => {
    expect((await annonces!.derniereAnnonce("fr"))?.texte).toBe("Deuxième annonce.");
  });
});

decrire()("rappels par e-mail", () => {
  it("n'existe pas avant consentement", async () => {
    expect(await rappels!.optinDuFoyer(foyer)).toBeUndefined();
  });

  it("enregistre le consentement en datant l'accord", async () => {
    await rappels!.activerRappels(foyer, "  Invite@Exemple.TEST ");
    const optin = await rappels!.optinDuFoyer(foyer);
    // L'adresse est normalisée : une casse différente ne crée pas un doublon.
    expect(optin?.email).toBe("invite@exemple.test");
    expect(optin?.consent_at).toBeInstanceOf(Date);
  });

  it("ne stocke pas le jeton de désinscription en clair", async () => {
    const { jetonDesinscription } = await rappels!.activerRappels(foyer, "invite@exemple.test");
    const lignes = await client!.query<{ n: number }>(
      `select count(*)::int as n from public.reminder_optin
        where unsubscribe_token_sha256::text like $1`,
      [`%${jetonDesinscription}%`],
    );
    expect(Number(lignes.rows[0]?.n)).toBe(0);
  });

  it("se désinscrit une seule fois, par le lien de l'e-mail", async () => {
    const { jetonDesinscription } = await rappels!.activerRappels(foyer, "invite@exemple.test");
    expect(await rappels!.desinscrireParJeton(jetonDesinscription)).toBe(true);
    // Deuxième passage : plus rien à désinscrire.
    expect(await rappels!.desinscrireParJeton(jetonDesinscription)).toBe(false);
    expect(await rappels!.optinDuFoyer(foyer)).toBeUndefined();
  });

  it("met la confirmation en file avec son lien de désinscription", async () => {
    await client!.query("delete from public.emails");
    await rappels!.envoyerConfirmation("invite@exemple.test", "https://exemple.test/desabonner/xyz");
    const attente = await email!.filePendante();
    expect(attente).toHaveLength(1);
    expect(attente[0]?.destinataire).toBe("invite@exemple.test");
    expect(attente[0]?.corps).toContain("https://exemple.test/desabonner/xyz");
  });
});

decrire()("file d'envoi", () => {
  it("marque envoyé ce qui est parti", async () => {
    await client!.query("delete from public.emails");
    await email!.mettreEnFile("un@exemple.test", "Sujet", "Corps");
    const bilan = await email!.viderFile(async () => undefined);
    expect(bilan).toEqual({ envoyes: 1, echecs: 0 });
    expect(await email!.filePendante()).toHaveLength(0);
  });

  it("garde en file ce qui a échoué, et abandonne après cinq tentatives", async () => {
    await client!.query("delete from public.emails");
    await email!.mettreEnFile("deux@exemple.test", "Sujet", "Corps");

    const echouer = async (): Promise<void> => {
      throw new Error("prestataire injoignable");
    };
    for (let essai = 0; essai < 4; essai += 1) {
      const bilan = await email!.viderFile(echouer);
      expect(bilan.echecs).toBe(1);
      // Toujours en file : rien n'est perdu.
      expect(await email!.filePendante()).toHaveLength(1);
    }
    await email!.viderFile(echouer);
    expect(await email!.filePendante()).toHaveLength(0);

    const ligne = await client!.query<{ statut: string; tentatives: number; erreur: string }>(
      "select statut, tentatives, erreur from public.emails",
    );
    expect(ligne.rows[0]?.statut).toBe("echec");
    expect(Number(ligne.rows[0]?.tentatives)).toBe(5);
    expect(ligne.rows[0]?.erreur).toContain("injoignable");
  });

  it("purge les e-mails envoyés depuis plus de trente jours", async () => {
    await client!.query("delete from public.emails");
    await email!.mettreEnFile("trois@exemple.test", "Sujet", "Corps");
    await client!.query(
      "update public.emails set statut = 'envoye', envoye_le = now() - interval '40 days'",
    );
    const r = await client!.query<{ purger_emails: number }>("select jl.purger_emails()");
    expect(Number(r.rows[0]?.purger_emails)).toBe(1);
  });
});
