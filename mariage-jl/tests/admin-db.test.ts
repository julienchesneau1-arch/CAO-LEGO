import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Accès administrateur : lien à usage unique, expiration, révocation.
 * Vérifié contre un vrai PostgreSQL, avec le code réel de lib/admin.ts.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_admin_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let admin: typeof import("@/lib/admin") | undefined;

const MARIES = "maries@exemple.test";
const REGIE = "regie@exemple.test";

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
  await client.query(
    `insert into public.admin_users (email, role) values ($1, 'admin'), ($2, 'regie')`,
    [MARIES, REGIE],
  );

  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_COOKIE_SECRET"] = "secret-de-test-pour-l-admin-0123456789";
  admin = await import("@/lib/admin");
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("lien d'accès administrateur", () => {
  it("n'est créé que pour une adresse de la liste blanche", async () => {
    expect(await admin!.creerLienMagique("inconnu@exemple.test")).toBeUndefined();
    expect(await admin!.creerLienMagique(MARIES)).toBeTypeOf("string");
  });

  it("ouvre une session une seule fois", async () => {
    const jeton = await admin!.creerLienMagique(MARIES);
    expect(jeton).toBeTypeOf("string");
    const premiere = await admin!.consommerLienMagique(jeton as string);
    expect(premiere?.email).toBe(MARIES);
    expect(premiere?.role).toBe("admin");
    // Deuxième tentative : le lien est mort.
    expect(await admin!.consommerLienMagique(jeton as string)).toBeUndefined();
  });

  it("ne stocke pas le jeton en clair", async () => {
    const jeton = (await admin!.creerLienMagique(MARIES)) as string;
    const lignes = await client!.query<{ n: number }>(
      `select count(*)::int as n from public.admin_magic_links where token_sha256::text like $1`,
      [`%${jeton}%`],
    );
    expect(Number(lignes.rows[0]?.n)).toBe(0);
  });

  it("refuse un lien expiré", async () => {
    const jeton = (await admin!.creerLienMagique(MARIES)) as string;
    await client!.query("update public.admin_magic_links set expires_at = now() - interval '1 minute'");
    expect(await admin!.consommerLienMagique(jeton)).toBeUndefined();
  });

  it("refuse un lien dont le compte a été révoqué entre-temps", async () => {
    const jeton = (await admin!.creerLienMagique(REGIE)) as string;
    await client!.query("update public.admin_users set revoked_at = now() where email = $1", [REGIE]);
    expect(await admin!.consommerLienMagique(jeton)).toBeUndefined();
    await client!.query("update public.admin_users set revoked_at = null where email = $1", [REGIE]);
  });

  it("donne à la régie son rôle, pas celui des mariés", async () => {
    const jeton = (await admin!.creerLienMagique(REGIE)) as string;
    const session = await admin!.consommerLienMagique(jeton);
    expect(session?.role).toBe("regie");
  });

  it("purge les liens périmés depuis plus d'une semaine", async () => {
    await client!.query(
      `update public.admin_magic_links set expires_at = now() - interval '30 days'`,
    );
    const avant = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.admin_magic_links",
    );
    expect(Number(avant.rows[0]?.n)).toBeGreaterThan(0);
    await client!.query("select jl.purger_liens_admin()");
    const apres = await client!.query<{ n: number }>(
      "select count(*)::int as n from public.admin_magic_links",
    );
    expect(Number(apres.rows[0]?.n)).toBe(0);
  });
});

decrire()("session administrateur signée", () => {
  it("ne se laisse pas réécrire", () => {
    const signee = admin!.signerSessionAdmin({
      email: MARIES,
      role: "admin",
      exp: Math.floor(Date.now() / 1000) + 600,
    });
    const [charge, signature] = signee.split(".");
    expect(charge).toBeTypeOf("string");
    const falsifiee = Buffer.from(
      JSON.stringify({ email: "pirate@exemple.test", role: "admin", exp: 9_999_999_999 }),
      "utf8",
    ).toString("base64url");
    expect(`${falsifiee}.${signature}`).not.toBe(signee);
  });
});
