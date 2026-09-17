import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";
import { BASE_E2E, FOYER, URL_ADMIN, URL_E2E } from "./fixtures";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const empreinte = (secret: string): Buffer =>
  createHash("sha256").update(secret.trim().toLowerCase(), "utf8").digest();

/** Base jetable, migrations réelles, un foyer d'essai. Rien de simulé. */
export default async function preparer(): Promise<void> {
  const gestion = new Client({ connectionString: URL_ADMIN });
  await gestion.connect();
  await gestion.query(`drop database if exists ${BASE_E2E}`);
  await gestion.query(`create database ${BASE_E2E}`);
  await gestion.end();

  const client = new Client({ connectionString: URL_E2E });
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
     values ($1, $2, $3) returning id`,
    [FOYER.label, empreinte(FOYER.jeton), empreinte(FOYER.code)],
  );
  await client.query(
    `insert into public.guests (household_id, first_name) values ($1, $2)`,
    [rows[0]?.id, FOYER.invite],
  );
  await client.end();
}
