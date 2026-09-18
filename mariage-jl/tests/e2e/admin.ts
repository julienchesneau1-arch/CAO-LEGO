import type { Browser, Page } from "@playwright/test";
import { createHash, randomBytes } from "node:crypto";
import { Client } from "pg";
import { BASE_URL, URL_E2E } from "./fixtures";

/**
 * Ouvre une session « mariés » dans son propre contexte. Le lien magique est
 * posé directement en base : les parcours testent l'écran, pas l'acheminement
 * du lien — celui-ci est déjà couvert par tests/admin-db.test.ts.
 */
export async function ouvrirAdmin(navigateur: Browser): Promise<Page> {
  const jeton = randomBytes(20).toString("hex");
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    await client.query(
      `insert into public.admin_users (email, role) values ('maries@e2e.test', 'admin')
       on conflict (email) do update set revoked_at = null`,
    );
    await client.query(
      `insert into public.admin_magic_links (email, token_sha256, expires_at)
       values ('maries@e2e.test', $1, now() + interval '30 minutes')`,
      [createHash("sha256").update(jeton).digest()],
    );
  } finally {
    await client.end();
  }

  const contexte = await navigateur.newContext({ baseURL: BASE_URL });
  const page = await contexte.newPage();
  await page.goto(`/admin/entrer?jeton=${jeton}`);
  return page;
}
