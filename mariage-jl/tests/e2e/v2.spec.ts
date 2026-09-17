import { expect, test } from "@playwright/test";
import { Client } from "pg";
import { BASE_URL, FOYER, URL_E2E } from "./fixtures";
import { reinitialiserFoyer } from "./reinitialiser";

/**
 * V2 : « Le texte », les messages des absents et « La promesse ».
 * Ce qui compte ici, c'est qu'un vœu scellé soit réellement illisible côté
 * serveur — pas seulement annoncé comme tel.
 */
const enBase = async <T extends Record<string, unknown>>(sql: string): Promise<T[]> => {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    return (await client.query<T>(sql)).rows;
  } finally {
    await client.end();
  }
};

test.beforeEach(async () => {
  await reinitialiserFoyer();
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query("delete from public.promises");
  await client.query("delete from public.absent_messages");
  await client.query("delete from public.announcements");
  await client.query("delete from public.emails");
  await client.query("delete from public.reminder_optin");
  await client.query("delete from public.admin_magic_links");
  await client.end();
});

test("« Le texte » se lit dans les deux sens", async ({ page }) => {
  await page.goto("/le-texte");

  // On cible la liste du texte, pas les onglets de navigation.
  const lignes = page.getByRole("list", { name: "Le texte" }).getByRole("listitem");
  await expect(lignes).toHaveCount(14);
  await expect(lignes.first()).toContainText("Julien et Lauriane vont se marier.");
  await expect(lignes.last()).toContainText("plus amoureux qu’en 2018.");

  await page.getByRole("button", { name: "Sauf que…" }).click();

  // Les mêmes lignes, dans l'autre sens : aucune n'est ajoutée ni retirée.
  await expect(lignes).toHaveCount(14);
  await expect(lignes.first()).toContainText("plus amoureux qu’en 2018.");
  await expect(lignes.last()).toContainText("Julien et Lauriane vont se marier.");
});

test("un absent peut laisser un mot, privé par défaut", async ({ page }) => {
  await page.goto("/loin");
  await page.locator('textarea[name="message"]').fill("Nous pensons à vous très fort.");

  const traite = page.waitForResponse((r) => r.request().method() === "POST");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await traite;

  await expect(page.getByText("C’est envoyé. Merci.")).toBeVisible();
  const lignes = await enBase<{ body: string; visibility: string }>(
    "select body, visibility from public.absent_messages",
  );
  expect(lignes[0]?.body).toContain("très fort");
  expect(lignes[0]?.visibility).toBe("private");
});

test("un vœu scellé est illisible du serveur", async ({ page }) => {
  const VOEU = "Gardez cette légèreté, même les jours gris. Et dansez souvent.";

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/promesse");

  await page.locator("textarea").fill(VOEU);
  const traite = page.waitForResponse((r) => r.url().includes("/promesse/sceller"));
  await page.getByRole("button", { name: "Sceller" }).click();
  expect((await traite).status()).toBe(204);

  await expect(page.getByText("Votre vœu est scellé.")).toBeVisible();

  const lignes = await enBase<{ ciphertext: string; sealed_until: Date }>(
    "select ciphertext, sealed_until from public.promises",
  );
  expect(lignes).toHaveLength(1);
  const enveloppe = lignes[0]?.ciphertext ?? "";
  expect(enveloppe).not.toContain(VOEU);
  for (const mot of ["légèreté", "dansez", "gris"]) {
    expect(enveloppe).not.toContain(mot);
  }
  expect(JSON.parse(enveloppe)).toMatchObject({ v: 1 });
  expect(lignes[0]?.sealed_until.toISOString().slice(0, 10)).toBe("2029-06-03");

  // Rien ne compte les participations : aucun nombre à l'écran (§17).
  await expect(page.getByText(/\d+\s+(vœu|voeu|promesse)/i)).toHaveCount(0);
});

test("le vœu n'est jamais rattaché à un foyer", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/promesse");
  await page.locator("textarea").fill("Un mot anonyme, et c'est voulu.");
  const traite = page.waitForResponse((r) => r.url().includes("/promesse/sceller"));
  await page.getByRole("button", { name: "Sceller" }).click();
  await traite;

  // La table des vœux ne porte aucune colonne de foyer : impossible de
  // deviner qui a écrit quoi, même avec l'accès à la base.
  const colonnes = await enBase<{ column_name: string }>(
    `select column_name from information_schema.columns
      where table_schema = 'public' and table_name = 'promises'`,
  );
  expect(colonnes.map((c) => c.column_name)).not.toContain("household_id");
});

test("une annonce publiée apparaît dans le fil et sur l'accueil", async ({ page, browser }) => {
  // Côté mariés : publier.
  const jetonAdmin = await (async () => {
    const client = new Client({ connectionString: URL_E2E });
    await client.connect();
    try {
      await client.query(
        `insert into public.admin_users (email, role) values ('maries@e2e.test', 'admin')
         on conflict (email) do update set revoked_at = null`,
      );
      // Jeton de lien magique posé directement : le parcours teste l'annonce,
      // pas l'envoi du lien.
      const jeton = "annonce2parcours3admin4jeton5lien67";
      const { createHash } = await import("node:crypto");
      await client.query(
        `insert into public.admin_magic_links (email, token_sha256, expires_at)
         values ('maries@e2e.test', $1, now() + interval '30 minutes')`,
        [createHash("sha256").update(jeton).digest()],
      );
      return jeton;
    } finally {
      await client.end();
    }
  })();

  const maries = await browser.newContext({ baseURL: BASE_URL });
  const pageMaries = await maries.newPage();
  await pageMaries.goto(`/admin/entrer?jeton=${jetonAdmin}`);
  await pageMaries.goto("/admin/annonces");
  await pageMaries.locator('textarea[name="texte_fr"]').fill("Le cocktail est servi sur la terrasse.");
  await pageMaries.locator('textarea[name="texte_en"]').fill("Cocktails are served on the terrace.");
  const publie = pageMaries.waitForResponse((r) => r.request().method() === "POST");
  await pageMaries.getByRole("button", { name: "Publier" }).click();
  await publie;
  await expect(pageMaries.getByText("Annonce publiée.")).toBeVisible();
  await maries.close();

  // Côté invité : le fil, puis l'accueil.
  await page.goto("/annonces");
  await expect(page.getByText("Le cocktail est servi sur la terrasse.")).toBeVisible();

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText("Le cocktail est servi sur la terrasse.")).toBeVisible();
});

test("les rappels e-mail ne partent qu'après consentement, et s'arrêtent en un tap", async ({
  page,
}) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/reponse");

  // Les rappels ne sont proposés qu'à un foyer qui vient : on répond d'abord.
  const repondu = page.waitForResponse((r) => r.url().includes("/reponse/statut"));
  await page.getByRole("button", { name: "Oui", exact: true }).click();
  await repondu;

  // Rien en file avant le consentement.
  expect(await enBase("select 1 from public.emails")).toHaveLength(0);

  await page.locator('input[name="email"]').fill("invite@parcours.test");
  const active = page.waitForResponse((r) => r.request().method() === "POST");
  await page.getByRole("button", { name: "Recevoir les rappels" }).click();
  await active;

  await expect(page.getByText("invite@parcours.test").first()).toBeVisible();
  const files = await enBase<{ destinataire: string; corps: string }>(
    "select destinataire, corps from public.emails",
  );
  expect(files).toHaveLength(1);
  expect(files[0]?.destinataire).toBe("invite@parcours.test");
  expect(files[0]?.corps).toContain("/desabonner/");

  // Le lien de l'e-mail désinscrit en un tap, sans rien demander.
  const lien = /\/desabonner\/[a-z2-9]+/.exec(files[0]?.corps ?? "")?.[0] ?? "";
  expect(lien).not.toBe("");
  await page.goto(lien);
  await expect(page.getByRole("heading", { name: "C’est fait" })).toBeVisible();
  expect(await enBase("select 1 from public.reminder_optin where revoked_at is null")).toHaveLength(
    0,
  );
});
