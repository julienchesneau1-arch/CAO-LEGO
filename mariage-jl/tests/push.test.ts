import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Notifications : ce qui est vérifié ici, c'est le seul comportement qui
 * pourrait dégrader le service avec le temps — un abonnement périmé doit
 * disparaître, sinon la liste grossit et chaque envoi ralentit.
 *
 * Le service de notification du navigateur n'est pas joignable depuis un test :
 * c'est `web-push` qui est remplacé, pas notre code.
 */
const envois: Array<{ endpoint: string }> = [];
let echouerPour: string | undefined;

vi.mock("web-push", () => ({
  default: {
    setVapidDetails: () => undefined,
    sendNotification: async (abonnement: { endpoint: string }) => {
      if (abonnement.endpoint === echouerPour) {
        throw Object.assign(new Error("abonnement périmé"), { statusCode: 410 });
      }
      envois.push({ endpoint: abonnement.endpoint });
    },
  },
}));

const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_push_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let push: typeof import("@/lib/push") | undefined;

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
     values ('Foyer push', $1, $2) returning id`,
    [
      createHash("sha256").update("jeton-push").digest(),
      createHash("sha256").update("code-push").digest(),
    ],
  );

  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_VAPID_CLE_PUBLIQUE"] = "cle-publique-de-test";
  process.env["JL_VAPID_CLE_PRIVEE"] = "cle-privee-de-test";
  process.env["JL_VAPID_CONTACT"] = "mailto:test@exemple.test";
  push = await import("@/lib/push");

  for (const nom of ["valide", "perime"]) {
    await push.enregistrerAbonnement(rows[0]?.id ?? "", {
      endpoint: `https://notifications.exemple.test/${nom}`,
      keys: { p256dh: "cle-publique-abonnement-de-test", auth: "secret-abonnement" },
    });
  }
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("notifications", () => {
  it("envoie à chaque abonné", async () => {
    envois.length = 0;
    echouerPour = undefined;
    const bilan = await push!.notifier("Julien & Lauriane", "Le cocktail est servi.", "/annonces");
    expect(bilan).toEqual({ envoyes: 2, perimes: 0 });
    expect(envois).toHaveLength(2);
  });

  it("supprime un abonnement périmé plutôt que de le réessayer sans fin", async () => {
    envois.length = 0;
    echouerPour = "https://notifications.exemple.test/perime";
    const bilan = await push!.notifier("Julien & Lauriane", "Deuxième annonce.");
    expect(bilan).toEqual({ envoyes: 1, perimes: 1 });

    const restants = await client!.query<{ endpoint: string }>(
      "select endpoint from public.push_subscription",
    );
    expect(restants.rows.map((l) => l.endpoint)).toEqual([
      "https://notifications.exemple.test/valide",
    ]);
  });

  it("n'enregistre pas deux fois le même abonnement", async () => {
    const avant = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.push_subscription",
    );
    const foyer = await client!.query<{ id: string }>("select id from public.households limit 1");
    await push!.enregistrerAbonnement(foyer.rows[0]?.id ?? "", {
      endpoint: "https://notifications.exemple.test/valide",
      keys: { p256dh: "autre-cle", auth: "autre-secret" },
    });
    const apres = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.push_subscription",
    );
    expect(Number(apres.rows[0]?.n)).toBe(Number(avant.rows[0]?.n));
  });

  it("dit clairement quand les clés manquent, au lieu d'échouer à l'envoi", async () => {
    const memoire = process.env["JL_VAPID_CLE_PRIVEE"];
    delete process.env["JL_VAPID_CLE_PRIVEE"];
    // L'environnement est mis en cache : on recharge le module pour le relire.
    vi.resetModules();
    const rechargé = await import("@/lib/push");
    expect(rechargé.pushConfigure()).toBe(false);
    await expect(rechargé.notifier("Titre", "Corps")).rejects.toThrow(/clés VAPID/);
    process.env["JL_VAPID_CLE_PRIVEE"] = memoire;
  });
});
