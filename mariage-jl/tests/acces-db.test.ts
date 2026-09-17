import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";
import { empreinte, genererCodeSecours, genererJeton } from "@/lib/acces";

/**
 * Accès des invités, vérifié contre un vrai PostgreSQL : recherche par
 * empreinte, code de secours, lien de partage qui s'épuise, limitation de
 * débit, traçabilité d'ouverture. Rien n'est simulé.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_acces_test";

let client: Client | undefined;
let indisponible: string | undefined;

const JETON = genererJeton();
const CODE = genererCodeSecours();
let foyerId = "";

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

  client = new Client({ connectionString: new URL(`/${BASE}`, URL_ADMIN).href });
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
     values ('Famille de test', $1, $2) returning id`,
    [empreinte(JETON), empreinte(CODE)],
  );
  foyerId = rows[0]?.id ?? "";
  await client.query(
    `insert into public.guests (household_id, first_name, last_name)
     values ($1, 'Camille', 'Dupré')`,
    [foyerId],
  );
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

/** Mêmes requêtes que lib/foyer.ts, à la lettre. */
const parJeton = (jeton: string) =>
  client!.query(
    `select id from public.households where token_sha256 = $1 and revoked_at is null`,
    [empreinte(jeton)],
  );

const parCode = (code: string) =>
  client!.query(
    `select id from public.households where backup_code_sha256 = $1 and revoked_at is null`,
    [empreinte(code)],
  );

decrire()("ouverture par QR", () => {
  it("retrouve le foyer par l'empreinte du jeton", async () => {
    const r = await parJeton(JETON);
    expect(r.rows[0]).toEqual({ id: foyerId });
  });

  it("ne stocke pas le jeton en clair", async () => {
    const r = await client!.query<{ n: number }>(
      `select count(*)::int as n from public.households where token_sha256::text like $1`,
      [`%${JETON}%`],
    );
    expect(Number(r.rows[0]?.n)).toBe(0);
  });

  it("refuse un jeton inconnu", async () => {
    expect((await parJeton(genererJeton())).rowCount).toBe(0);
  });

  it("refuse un foyer révoqué, puis le rétablit", async () => {
    await client!.query(`update public.households set revoked_at = now() where id = $1`, [foyerId]);
    expect((await parJeton(JETON)).rowCount).toBe(0);
    await client!.query(`update public.households set revoked_at = null where id = $1`, [foyerId]);
    expect((await parJeton(JETON)).rowCount).toBe(1);
  });

  it("note la première ouverture une seule fois et rafraîchit la dernière visite", async () => {
    await client!.query("select jl.marquer_ouverture($1)", [foyerId]);
    const premier = await client!.query<{ first_opened_at: Date; last_seen_at: Date }>(
      `select first_opened_at, last_seen_at from public.households where id = $1`,
      [foyerId],
    );
    await client!.query("select jl.marquer_ouverture($1)", [foyerId]);
    const second = await client!.query<{ first_opened_at: Date; last_seen_at: Date }>(
      `select first_opened_at, last_seen_at from public.households where id = $1`,
      [foyerId],
    );
    expect(second.rows[0]?.first_opened_at).toEqual(premier.rows[0]?.first_opened_at);
    expect(second.rows[0]?.last_seen_at?.getTime()).toBeGreaterThanOrEqual(
      premier.rows[0]?.last_seen_at?.getTime() ?? 0,
    );
  });
});

decrire()("code de secours", () => {
  it("accepte le code saisi en minuscules et avec des espaces", async () => {
    const r = await parCode(` ${CODE.toLowerCase()} `);
    expect(r.rows[0]).toEqual({ id: foyerId });
  });

  it("refuse un code voisin", async () => {
    expect((await parCode(genererCodeSecours())).rowCount).toBe(0);
  });
});

decrire()("lien de partage du foyer", () => {
  const consommer = (jeton: string) =>
    client!.query(
      `with lien as (
         update public.household_links set opens = opens + 1
          where token_sha256 = $1 and revoked_at is null
            and expires_at > now() and opens < max_opens
          returning household_id
       )
       select h.id from public.households h join lien on lien.household_id = h.id
        where h.revoked_at is null`,
      [empreinte(jeton)],
    );

  it("s'épuise après le nombre d'ouvertures prévu", async () => {
    const jeton = genererJeton();
    await client!.query(
      `insert into public.household_links (household_id, token_sha256, max_opens, expires_at)
       values ($1, $2, 2, now() + interval '30 days')`,
      [foyerId, empreinte(jeton)],
    );
    expect((await consommer(jeton)).rowCount).toBe(1);
    expect((await consommer(jeton)).rowCount).toBe(1);
    expect((await consommer(jeton)).rowCount).toBe(0);
  });

  it("refuse un lien expiré", async () => {
    const jeton = genererJeton();
    await client!.query(
      `insert into public.household_links (household_id, token_sha256, max_opens, expires_at)
       values ($1, $2, 5, now() - interval '1 minute')`,
      [foyerId, empreinte(jeton)],
    );
    expect((await consommer(jeton)).rowCount).toBe(0);
  });

  it("refuse un lien révoqué depuis l'admin", async () => {
    const jeton = genererJeton();
    await client!.query(
      `insert into public.household_links (household_id, token_sha256, max_opens, expires_at, revoked_at)
       values ($1, $2, 5, now() + interval '30 days', now())`,
      [foyerId, empreinte(jeton)],
    );
    expect((await consommer(jeton)).rowCount).toBe(0);
  });
});

decrire()("limitation de débit", () => {
  it("laisse passer cinq essais par heure, puis refuse", async () => {
    const resultats: boolean[] = [];
    for (let i = 0; i < 6; i += 1) {
      const r = await client!.query<{ autorise: boolean }>(
        "select jl.tentative_autorisee($1, $2::interval, $3) as autorise",
        ["retrouver:test", "1 hour", 5],
      );
      resultats.push(r.rows[0]?.autorise ?? false);
    }
    expect(resultats).toEqual([true, true, true, true, true, false]);
  });

  it("compte séparément deux appelants", async () => {
    const r = await client!.query<{ autorise: boolean }>(
      "select jl.tentative_autorisee($1, $2::interval, $3) as autorise",
      ["retrouver:autre", "1 hour", 5],
    );
    expect(r.rows[0]?.autorise).toBe(true);
  });

  it("n'est pas appelable depuis l'interface", async () => {
    await client!.query("begin");
    try {
      await client!.query("set local role authenticated");
      await expect(
        client!.query("select jl.tentative_autorisee('x', '1 hour', 5)"),
      ).rejects.toThrow(/permission denied/i);
    } finally {
      await client!.query("rollback");
    }
  });
});
