import { expect, test } from "@playwright/test";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import { reinitialiserContenus, reinitialiserFoyer } from "./reinitialiser";

/**
 * V3 — plan de table. Les mariés posent les tables, l'invité trouve la
 * sienne, et la recherche ne dit rien de plus qu'un prénom et une table.
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
  await reinitialiserContenus();
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query("delete from public.seating_assign");
  await client.query("delete from public.seating_tables");
  // Les invités ajoutés par un parcours précédent sont retirés : le compteur
  // « sans table » serait faux, et les deux gabarits partagent la base.
  await client.query("delete from public.guests where first_name <> $1", [FOYER.invite]);
  await client.end();
});

test("sans plan de table, l'écran le dit au lieu de rester vide", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/ma-table");
  await expect(page.getByText("Le plan de table sera publié avant le jour J.")).toBeVisible();
});

test("les mariés créent une table, l'invité trouve la sienne", async ({ page, browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/table");
  await expect(maries.getByText("Aucune table pour l’instant.")).toBeVisible();

  await maries.locator('input[name="label"]').fill("Table des vignes");
  await maries.locator('input[name="capacite"]').fill("8");
  const cree = maries.waitForResponse((r) => r.url().includes("/admin/table/creer"));
  await maries.getByRole("button", { name: "Créer" }).click();
  await cree;
  await expect(maries.getByText("Enregistré.")).toBeVisible();

  // Puis on pose l'invité de ce foyer.
  await expect(maries.getByText("1 personne(s) sans table.")).toBeVisible();
  const formulaire = maries.locator('form[action="/admin/table/placer"]').first();
  await formulaire.locator("select").selectOption({ label: "Table des vignes" });
  const pose = maries.waitForResponse((r) => r.url().includes("/admin/table/placer"));
  await formulaire.getByRole("button", { name: "Enregistrer" }).click();
  await pose;
  await expect(maries.getByText("Tout le monde est placé.")).toBeVisible();
  await maries.context().close();

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/ma-table");
  await expect(page.getByText("Table Table des vignes")).toBeVisible();
  await expect(page.getByText(FOYER.invite, { exact: true })).toBeVisible();
});

test("la recherche trouve un prénom sans accent, et ne dit que sa table", async ({
  page,
  browser,
}) => {
  // Un deuxième invité, au prénom accentué.
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query(
    `insert into public.guests (household_id, first_name, sort_order)
     select id, 'Chloé', 9 from public.households limit 1
     on conflict do nothing`,
  );
  await client.end();

  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/table");
  await maries.locator('input[name="label"]').fill("Table 3");
  const cree = maries.waitForResponse((r) => r.url().includes("/admin/table/creer"));
  await maries.getByRole("button", { name: "Créer" }).click();
  await cree;

  const ligne = maries
    .locator("li")
    .filter({ hasText: "Chloé" })
    .locator('form[action="/admin/table/placer"]');
  await ligne.locator("select").selectOption({ label: "Table 3" });
  const pose = maries.waitForResponse((r) => r.url().includes("/admin/table/placer"));
  await ligne.getByRole("button", { name: "Enregistrer" }).click();
  await pose;
  await maries.context().close();

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/ma-table");

  await page.locator('input[name="q"]').fill("chloe");
  await page.getByRole("button", { name: "Chercher quelqu’un" }).click();
  // On cible la section de recherche : « Chloé » figure aussi dans la liste
  // des convives de la table du foyer.
  const resultats = page.getByRole("region", { name: "Chercher quelqu’un" });
  await expect(resultats.getByText("Chloé")).toBeVisible();
  await expect(resultats.getByText("Table Table 3")).toBeVisible();

  // Rien de plus que le prénom et la table : pas de nom de foyer.
  await expect(page.getByText(FOYER.label)).toHaveCount(0);

  // Un prénom inconnu ne donne rien, et le dit.
  await page.locator('input[name="q"]').fill("zzzz");
  await page.getByRole("button", { name: "Chercher quelqu’un" }).click();
  await expect(page.getByText("Personne de ce nom dans le plan de table.")).toBeVisible();
});

test("supprimer une table libère ses convives sans supprimer personne", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/table");
  await maries.locator('input[name="label"]').fill("Table éphémère");
  const cree = maries.waitForResponse((r) => r.url().includes("/admin/table/creer"));
  await maries.getByRole("button", { name: "Créer" }).click();
  await cree;

  const formulaire = maries.locator('form[action="/admin/table/placer"]').first();
  await formulaire.locator("select").selectOption({ label: "Table éphémère" });
  const pose = maries.waitForResponse((r) => r.url().includes("/admin/table/placer"));
  await formulaire.getByRole("button", { name: "Enregistrer" }).click();
  await pose;

  const supprime = maries.waitForResponse((r) => r.url().includes("/admin/table/supprimer"));
  await maries.getByRole("button", { name: "Supprimer" }).first().click();
  await supprime;
  await expect(maries.getByText("Supprimé.")).toBeVisible();

  // La personne existe toujours ; elle est seulement sans table.
  expect(await enBase("select 1 from public.seating_assign")).toHaveLength(0);
  expect((await enBase("select 1 from public.guests")).length).toBeGreaterThan(0);
  await maries.context().close();
});

test("les cartes de table et la fiche régie se téléchargent en PDF", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/table");
  await maries.locator('input[name="label"]').fill("Table 1");
  const cree = maries.waitForResponse((r) => r.url().includes("/admin/table/creer"));
  await maries.getByRole("button", { name: "Créer" }).click();
  await cree;

  for (const chemin of ["/admin/table/cartes", "/admin/table/fiche"]) {
    const reponse = await maries.request.get(chemin, {
      headers: {
        cookie: (await maries.context().cookies())
          .map((c) => `${c.name}=${c.value}`)
          .join("; "),
      },
    });
    expect(reponse.status(), chemin).toBe(200);
    expect(reponse.headers()["content-type"], chemin).toContain("application/pdf");
    const octets = await reponse.body();
    expect(octets.subarray(0, 4).toString("latin1"), chemin).toBe("%PDF");
    expect(octets.byteLength, chemin).toBeGreaterThan(2000);
  }
  await maries.context().close();
});
