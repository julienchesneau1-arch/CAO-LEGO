#!/usr/bin/env node
/**
 * Lien d'accès à l'espace des mariés.
 *
 * Le brief §6 prévoit un lien magique par e-mail ; le prestataire n'est pas
 * encore choisi (question V1-03). En attendant, ce script produit le même
 * jeton à usage unique, à remettre de la main à la main.
 *
 *   node scripts/admin-lien.mjs julien@exemple.fr
 *   node scripts/admin-lien.mjs lauriane@exemple.fr --inviter
 *   node scripts/admin-lien.mjs regie@exemple.fr --inviter --role regie
 */
import { createHash, randomBytes } from "node:crypto";
import pg from "pg";

const arguments_ = process.argv.slice(2);
const email = arguments_.find((a) => !a.startsWith("--"))?.trim().toLowerCase();
const inviter = arguments_.includes("--inviter");
const role = arguments_[arguments_.indexOf("--role") + 1];
const roleFinal = arguments_.includes("--role") ? role : "admin";
const base = process.env.JL_DATABASE_URL;
const hote = process.env.JL_URL_PUBLIQUE ?? "http://localhost:3000";

if (email === undefined || !email.includes("@")) {
  console.error("Usage : node scripts/admin-lien.mjs <email> [--inviter] [--role admin|regie|tech]");
  process.exit(2);
}
if (base === undefined) {
  console.error("JL_DATABASE_URL est absent : voir .env.example.");
  process.exit(2);
}
if (!["admin", "regie", "tech"].includes(roleFinal)) {
  console.error(`Rôle inconnu : ${roleFinal}`);
  process.exit(2);
}

const ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789";
const jeton = Array.from(randomBytes(32), (octet) => ALPHABET[octet % ALPHABET.length]).join("");
const empreinte = createHash("sha256").update(jeton, "utf8").digest();

const client = new pg.Client({ connectionString: base });
await client.connect();
try {
  if (inviter) {
    await client.query(
      `insert into public.admin_users (email, role) values ($1, $2)
       on conflict (email) do update set role = excluded.role, revoked_at = null`,
      [email, roleFinal],
    );
  }
  const { rows } = await client.query(
    "select email from public.admin_users where email = $1 and revoked_at is null",
    [email],
  );
  if (rows.length === 0) {
    console.error(`« ${email} » n'est pas dans la liste blanche. Ajoutez --inviter.`);
    process.exit(1);
  }
  await client.query(
    `insert into public.admin_magic_links (email, token_sha256, expires_at)
     values ($1, $2, now() + interval '30 minutes')`,
    [email, empreinte],
  );
  console.log(`\nLien valable 30 minutes, à usage unique :\n\n  ${hote}/admin/entrer?jeton=${jeton}\n`);
} finally {
  await client.end();
}
