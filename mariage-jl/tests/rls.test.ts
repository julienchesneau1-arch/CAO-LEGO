import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Tests RLS — critère de fin de V0 (docs/PLAN.md §8).
 * Ils tournent contre un vrai PostgreSQL : rien n'est simulé. Le schéma `auth`
 * et les rôles anon / authenticated / service_role sont créés par
 * supabase/tests/00_compat_local.sql, qui reproduit ce que Supabase fournit.
 *
 * Sans base joignable, la suite est ignorée — sauf si JL_REQUIRE_DB=1
 * (intégration continue), où l'absence de base est une erreur.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_rls_test";

const ADMIN_ID = "11111111-1111-1111-1111-111111111111";
const REGIE_ID = "22222222-2222-2222-2222-222222222222";
const INCONNU_ID = "33333333-3333-3333-3333-333333333333";

let client: Client | undefined;
let indisponible: string | undefined;

const fichiersSql = (): string[] => [
  join(RACINE, "supabase", "tests", "00_compat_local.sql"),
  ...readdirSync(join(RACINE, "supabase", "migrations"))
    .filter((f) => f.endsWith(".sql"))
    .sort()
    .map((f) => join(RACINE, "supabase", "migrations", f)),
];

beforeAll(async () => {
  const gestion = new Client({ connectionString: URL_ADMIN });
  try {
    await gestion.connect();
  } catch (erreur) {
    indisponible = `PostgreSQL injoignable (${URL_ADMIN}) : ${(erreur as Error).message}`;
    if (process.env["JL_REQUIRE_DB"] === "1") throw new Error(indisponible);
    return;
  }
  await gestion.query(`drop database if exists ${BASE}`);
  await gestion.query(`create database ${BASE}`);
  await gestion.end();

  client = new Client({ connectionString: new URL(`/${BASE}`, URL_ADMIN).href });
  await client.connect();
  for (const fichier of fichiersSql()) {
    await client.query(readFileSync(fichier, "utf8"));
  }

  // Jeu d'essai minimal, posé en tant que propriétaire.
  await client.query(
    `insert into public.admin_users (email, user_id, role) values
       ('admin@exemple.test', $1, 'admin'),
       ('regie@exemple.test', $2, 'regie')`,
    [ADMIN_ID, REGIE_ID],
  );
  await client.query(
    `insert into public.households (id, label_public, token_sha256, backup_code_sha256)
     values (gen_random_uuid(), 'Foyer de test', sha256('jeton-test'), sha256('code-test'))`,
  );
  await client.query(
    `insert into public.guests (household_id, first_name)
     select id, 'Invité de test' from public.households limit 1`,
  );
  await client.query(
    `insert into public.health_allergies (guest_id, content, consent_at, consent_text_version, purge_after)
     select id, 'arachides', now(), 'v1', current_date - 1 from public.guests limit 1`,
  );
  await client.query(
    `insert into public.media (storage_path, kind, mime, bytes, moment_id, status)
     values ('test/photo.jpg', 'photo', 'image/jpeg', 1024, '03', 'published')`,
  );
  await client.query(`insert into public.promises (ciphertext) values ('chiffré')`);
  await client.query(
    `insert into public.audit_log (action, at) values ('test', now() - interval '40 days')`,
  );
}, 60_000);

afterAll(async () => {
  await client?.end();
});

/** Exécute `fn` sous un rôle donné, dans une transaction annulée ensuite. */
async function enTantQue<T>(
  role: "anon" | "authenticated" | "service_role",
  sub: string | null,
  fn: (c: Client) => Promise<T>,
): Promise<T> {
  if (!client) throw new Error(indisponible ?? "base absente");
  await client.query("begin");
  try {
    const claims = sub === null ? "{}" : JSON.stringify({ sub, role: "authenticated" });
    await client.query(`set local request.jwt.claims = '${claims}'`);
    await client.query(`set local role ${role}`);
    return await fn(client);
  } finally {
    await client.query("rollback");
  }
}

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("refus par défaut", () => {
  it("active et force la RLS sur toutes les tables publiques", async () => {
    const r = await client!.query<{ relname: string }>(
      `select c.relname from pg_class c
         join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'r'
          and (not c.relrowsecurity or not c.relforcerowsecurity)`,
    );
    expect(r.rows.map((l) => l.relname)).toEqual([]);
  });

  it("ne laisse aucun droit de table au rôle anonyme", async () => {
    const r = await client!.query<{ table_name: string }>(
      `select distinct table_name from information_schema.role_table_grants
        where grantee = 'anon' and table_schema = 'public'`,
    );
    expect(r.rows.map((l) => l.table_name)).toEqual([]);
  });

  it("interdit à un invité anonyme de lire les foyers", async () => {
    await expect(
      enTantQue("anon", null, (c) => c.query("select * from public.households")),
    ).rejects.toThrow(/permission denied/i);
  });

  it("interdit à un invité anonyme de lire les vœux", async () => {
    await expect(
      enTantQue("anon", null, (c) => c.query("select * from public.promises")),
    ).rejects.toThrow(/permission denied/i);
  });
});

decrire()("compte authentifié sans rôle attribué", () => {
  it("ne voit aucun moment", async () => {
    const r = await enTantQue("authenticated", INCONNU_ID, (c) =>
      c.query("select id from public.moments"),
    );
    expect(r.rowCount).toBe(0);
  });

  it("ne voit aucune allergie", async () => {
    const r = await enTantQue("authenticated", INCONNU_ID, (c) =>
      c.query("select guest_id from public.health_allergies"),
    );
    expect(r.rowCount).toBe(0);
  });
});

decrire()("régie", () => {
  it("lit les cinq moments", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query("select id from public.moments"),
    );
    expect(r.rowCount).toBe(5);
  });

  it("publie une annonce", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query(
        `insert into public.announcements (body_fr, body_en, author_role)
         values ('Le cocktail est servi.', 'Cocktails are served.', 'regie') returning id`,
      ),
    );
    expect(r.rowCount).toBe(1);
  });

  it("décale un moment", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query("update public.moments set shift_minutes = 15 where id = '03' returning id"),
    );
    expect(r.rowCount).toBe(1);
  });

  it("ne peut pas renommer un moment", async () => {
    await expect(
      enTantQue("authenticated", REGIE_ID, (c) =>
        c.query("update public.moments set name_fr = 'Autre' where id = '03'"),
      ),
    ).rejects.toThrow(/que le décalage et les horaires/i);
  });

  it("masque un média", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query("update public.media set status = 'hidden' returning id"),
    );
    expect(r.rowCount).toBe(1);
  });

  it("ne peut pas changer la provenance d'un média", async () => {
    await expect(
      enTantQue("authenticated", REGIE_ID, (c) =>
        c.query("update public.media set storage_path = 'ailleurs.jpg'"),
      ),
    ).rejects.toThrow(/que le statut/i);
  });

  it("ne voit aucune donnée personnelle de foyer", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query("select id from public.households"),
    );
    expect(r.rowCount).toBe(0);
  });

  it("ne voit aucune allergie", async () => {
    const r = await enTantQue("authenticated", REGIE_ID, (c) =>
      c.query("select guest_id from public.health_allergies"),
    );
    expect(r.rowCount).toBe(0);
  });
});

decrire()("admin", () => {
  it("voit les foyers et les invités", async () => {
    const r = await enTantQue("authenticated", ADMIN_ID, (c) =>
      c.query("select h.id, g.first_name from public.households h join public.guests g on g.household_id = h.id"),
    );
    expect(r.rowCount).toBe(1);
  });

  it("voit les allergies", async () => {
    const r = await enTantQue("authenticated", ADMIN_ID, (c) =>
      c.query("select content from public.health_allergies"),
    );
    expect(r.rows[0]).toEqual({ content: "arachides" });
  });

  it("édite un contenu", async () => {
    const r = await enTantQue("authenticated", ADMIN_ID, (c) =>
      c.query(
        `insert into public.content_blocks (key, locale, value)
         values ('test.bloc', 'fr', '"[À COMPLÉTER]"'::jsonb) returning key`,
      ),
    );
    expect(r.rowCount).toBe(1);
  });
});

decrire()("La promesse reste scellée", () => {
  it("est illisible même pour l'admin", async () => {
    await expect(
      enTantQue("authenticated", ADMIN_ID, (c) => c.query("select ciphertext from public.promises")),
    ).rejects.toThrow(/permission denied/i);
  });

  it("ne peut pas être supprimée depuis l'interface", async () => {
    await expect(
      enTantQue("authenticated", ADMIN_ID, (c) => c.query("delete from public.promises")),
    ).rejects.toThrow(/permission denied/i);
  });

  it("refuse une date de descellement différente du 3 juin 2029", async () => {
    await expect(
      client!.query(
        `insert into public.promises (ciphertext, sealed_until) values ('x', date '2028-06-04')`,
      ),
    ).rejects.toThrow(/promises_sealed_until_check/i);
  });

  it("n'est lisible que par le serveur, qui la stocke chiffrée", async () => {
    const r = await enTantQue("service_role", null, (c) =>
      c.query("select ciphertext from public.promises"),
    );
    expect(r.rows[0]).toEqual({ ciphertext: "chiffré" });
  });
});

decrire()("rétention", () => {
  it("supprime une allergie échue et garde une allergie à venir", async () => {
    await client!.query(
      `insert into public.guests (household_id, first_name)
       select id, 'Invité récent' from public.households limit 1`,
    );
    await client!.query(
      `insert into public.health_allergies (guest_id, content, consent_at, consent_text_version, purge_after)
       select id, 'gluten', now(), 'v1', current_date + 10 from public.guests
        where first_name = 'Invité récent'`,
    );
    const r = await client!.query<{ purger_allergies: number }>("select jl.purger_allergies()");
    expect(Number(r.rows[0]?.purger_allergies)).toBe(1);
    const reste = await client!.query("select content from public.health_allergies");
    expect(reste.rows).toEqual([{ content: "gluten" }]);
  });

  it("purge les journaux de plus de 30 jours", async () => {
    const r = await client!.query<{ purger_journaux: number }>("select jl.purger_journaux()");
    expect(Number(r.rows[0]?.purger_journaux)).toBe(1);
  });

  it("ne supprime pas les réponses avant 3 mois après le mariage", async () => {
    const r = await client!.query<{ purger_reponses: number }>("select jl.purger_reponses()");
    expect(Number(r.rows[0]?.purger_reponses)).toBe(0);
  });

  it("ne supprime un vœu que s'il a été remis", async () => {
    const avant = await client!.query<{ purger_voeux: number }>("select jl.purger_voeux()");
    expect(Number(avant.rows[0]?.purger_voeux)).toBe(0);
    await client!.query(
      `update public.promises set remise_le = now(), sealed_until = date '2029-06-03'`,
    );
    await client!.query(`update public.parametres set date_mariage = date '2028-06-03'`);
    const apres = await client!.query<{ n: number }>(
      `select count(*)::int as n from public.promises where remise_le is not null`,
    );
    expect(Number(apres.rows[0]?.n)).toBeGreaterThan(0);
  });
});

decrire()("hygiène des secrets", () => {
  it("ne stocke aucun jeton en clair", async () => {
    // Seule exception admise : `moments.color_token` designe une couleur,
    // pas un secret. Toute autre colonne « token » ou « code » doit etre un
    // hache binaire.
    const EXCEPTIONS = new Set(["moments.color_token"]);
    const r = await client!.query<{ table_name: string; column_name: string; data_type: string }>(
      `select table_name, column_name, data_type from information_schema.columns
        where table_schema = 'public' and (column_name like '%token%' or column_name like '%code%')`,
    );
    const secrets = r.rows.filter((c) => !EXCEPTIONS.has(`${c.table_name}.${c.column_name}`));
    expect(secrets.length).toBeGreaterThan(0);
    for (const colonne of secrets) {
      expect(`${colonne.table_name}.${colonne.column_name}`).toMatch(/sha256$/);
      expect(colonne.data_type).toBe("bytea");
    }
  });
});
