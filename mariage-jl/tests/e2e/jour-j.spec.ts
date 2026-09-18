import { expect, test } from "@playwright/test";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import {
  forcerPeriode,
  poserJourneeAutourDeMaintenant,
  reinitialiserContenus,
  reinitialiserFoyer,
} from "./reinitialiser";

/**
 * V3 — le jour J. Les parcours forcent la période et posent des horaires
 * autour de l'instant présent : c'est le seul moyen de vérifier « Maintenant »
 * et la cérémonie débranchée sans attendre le 3 juin 2028.
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
  await forcerPeriode(null);
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query("delete from public.announcements");
  await client.query("update public.parametres set photos_en_pause = false, ceremonie_debranchee = true");
  await client.end();
});

test.afterEach(async () => {
  await forcerPeriode(null);
});

test("le jour J, l'accueil devient « Maintenant » et nomme le moment en cours", async ({
  page,
}) => {
  await poserJourneeAutourDeMaintenant("03");
  await forcerPeriode("jour");

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  await expect(page.getByRole("heading", { name: "En ce moment" })).toBeVisible();
  await expect(page.getByText("La Rencontre")).toBeVisible();
  // Et le moment suivant, avec son compte à rebours discret.
  await expect(page.getByRole("heading", { name: "Ensuite" })).toBeVisible();
  await expect(page.getByText("L’Ivresse")).toBeVisible();
  await expect(page.getByText(/dans \d+ min/)).toBeVisible();

  // La barre du bas a basculé sur les onglets du jour J. On la cible par son
  // nom : le raccourci « Aide » de l'écran porte le même libellé.
  const barre = page.getByRole("navigation", { name: "Navigation" });
  await expect(barre.getByRole("link", { name: "Maintenant" })).toBeVisible();
  await expect(barre.getByRole("link", { name: "Aide" })).toBeVisible();
  await expect(barre.getByRole("link", { name: "Réponse" })).toHaveCount(0);
});

test("pendant la cérémonie, l'application demande de ranger son téléphone", async ({ page }) => {
  await poserJourneeAutourDeMaintenant("02");
  await forcerPeriode("jour");

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  await expect(page.getByRole("heading", { name: "Profitez de l’instant" })).toBeVisible();
  await expect(page.getByText(/Notre photographe s’occupe des images/)).toBeVisible();

  // Le même écran, un moment plus tard : la coupure s'est levée seule.
  await poserJourneeAutourDeMaintenant("03");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Profitez de l’instant" })).toHaveCount(0);
});

test("sans horaires saisis, « Maintenant » le dit au lieu d'inventer", async ({ page }) => {
  await forcerPeriode("jour");
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText(/Les horaires ne sont pas encore fixés/)).toBeVisible();
});

test("la semaine du mariage ajoute une checklist qui ne quitte pas le téléphone", async ({
  page,
}) => {
  await forcerPeriode("semaine");
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  await expect(page.getByRole("heading", { name: "Ma liste" })).toBeVisible();
  await expect(page.getByText("0 sur 6")).toBeVisible();

  await page.getByLabel("Ma tenue est prête").check();
  await page.getByLabel("J’ai une batterie externe pour les photos").check();
  await expect(page.getByText("2 sur 6")).toBeVisible();

  // Gardée d'une visite à l'autre, et nulle part ailleurs que dans le téléphone.
  await page.reload();
  await expect(page.getByText("2 sur 6")).toBeVisible();
  await expect(page.getByText("Cette liste ne quitte pas votre téléphone.")).toBeVisible();

  const stocke = await page.evaluate(() => localStorage.getItem("jl_checklist"));
  expect(stocke).toContain("tenue");
  // Rien n'est parti au serveur : aucune table ne porte de checklist.
  const colonnes = await enBase<{ table_name: string }>(
    `select table_name from information_schema.columns
      where table_schema = 'public' and column_name like '%checklist%'`,
  );
  expect(colonnes).toEqual([]);
});

test("l'aide n'affiche un bouton d'appel que si le numéro existe", async ({ page, browser }) => {
  await page.goto("/aide");
  await expect(page.getByText("Le numéro sera ajouté avant le jour J.").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Appeler/ })).toHaveCount(0);

  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=contacts");
  await maries.getByRole("link", { name: /L’équipe du jour/ }).click();
  await maries.locator('input[name="texte_fr"]').fill("Camille");
  await maries.locator('input[name="texte_en"]').fill("Camille");
  await maries.locator('input[name="telephone"]').fill("+33 6 12 34 56 78");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await maries.context().close();

  await page.goto("/aide");
  const appel = page.getByRole("link", { name: "Appeler Camille" });
  await expect(appel).toBeVisible();
  await expect(appel).toHaveAttribute("href", "tel:+33612345678");
});

test("un numéro qui ne se compose pas est refusé", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=contacts&element=aide.temoin");
  await maries.locator('input[name="texte_fr"]').fill("Un témoin");
  await maries.locator('input[name="texte_en"]').fill("A witness");
  await maries.locator('input[name="telephone"]').evaluate((champ: HTMLInputElement) => {
    champ.form?.setAttribute("novalidate", "novalidate");
  });
  await maries.locator('input[name="telephone"]').fill("appelez-moi");
  const refus = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await refus;
  await expect(maries.getByText("Ce numéro ne peut pas être composé.")).toBeVisible();
  await maries.context().close();
});

test("la régie décale un moment et tous les suivants", async ({ page, browser }) => {
  await poserJourneeAutourDeMaintenant("03");
  await forcerPeriode("jour");

  const avant = await enBase<{ id: string; heure: string }>(
    `select id, to_char(starts_at at time zone 'Europe/Paris', 'HH24:MI') as heure
       from public.moments order by id`,
  );

  const regie = await ouvrirAdmin(browser);
  await regie.goto("/regie");
  // Le pas est partagé : on le choisit une fois, puis on décale un moment.
  await regie.getByRole("link", { name: "15 min" }).click();
  const bloc = regie.locator('form[action="/regie/decaler"]').nth(3); // le quatrième moment
  const decale = regie.waitForResponse((r) => r.request().method() === "POST");
  await bloc.getByRole("button", { name: /Retarder de 15/ }).click();
  await decale;
  await expect(regie.getByText("Horaires décalés.")).toBeVisible();
  await regie.context().close();

  const apres = await enBase<{ id: string; shift_minutes: number }>(
    "select id, shift_minutes from public.moments order by id",
  );
  expect(apres.map((m) => m.shift_minutes)).toEqual([0, 0, 0, 15, 15]);

  // L'invité voit le nouvel horaire sur le programme, sans rien faire.
  await page.goto("/programme");
  const attendu = avant.find((m) => m.id === "03")?.heure;
  expect(attendu).toBeTruthy();
  await expect(page.getByText(`de ${attendu}`, { exact: false })).toBeVisible();
});

test("la régie publie une annonce à partir d'un modèle, traduite", async ({ page, browser }) => {
  const regie = await ouvrirAdmin(browser);
  await regie.goto("/regie");
  const publie = regie.waitForResponse((r) => r.request().method() === "POST");
  await regie.getByRole("button", { name: "Le cocktail est servi." }).click();
  await publie;
  await expect(regie.getByText("Annonce publiée.")).toBeVisible();
  await regie.context().close();

  const lignes = await enBase<{ body_fr: string; body_en: string; author_role: string }>(
    "select body_fr, body_en, author_role from public.announcements",
  );
  expect(lignes).toHaveLength(1);
  expect(lignes[0]?.body_fr).toBe("Le cocktail est servi.");
  // L'anglophone reçoit une vraie traduction, pas du français recopié.
  expect(lignes[0]?.body_en).toBe("Cocktails are served.");
  expect(lignes[0]?.author_role).toBe("regie");

  await page.goto("/annonces");
  await expect(page.getByText("Le cocktail est servi.")).toBeVisible();
});

test("la régie suspend puis rouvre l'envoi de souvenirs", async ({ browser }) => {
  await poserJourneeAutourDeMaintenant("04");
  const regie = await ouvrirAdmin(browser);
  await regie.goto("/regie");
  await expect(regie.getByText("Les envois sont ouverts.")).toBeVisible();

  const coupe = regie.waitForResponse((r) => r.request().method() === "POST");
  await regie.getByRole("button", { name: "Suspendre les envois" }).click();
  await coupe;
  await expect(regie.getByText("Les envois sont suspendus.")).toBeVisible();
  expect(
    (await enBase<{ photos_en_pause: boolean }>("select photos_en_pause from public.parametres"))[0]
      ?.photos_en_pause,
  ).toBe(true);

  const rouvre = regie.waitForResponse((r) => r.request().method() === "POST");
  await regie.getByRole("button", { name: "Rouvrir les envois" }).click();
  await rouvre;
  await expect(regie.getByText("Les envois sont ouverts.")).toBeVisible();
  await regie.context().close();
});

test("la régie n'est pas accessible sans lien, et n'apprend rien à qui insiste", async ({
  page,
}) => {
  await page.goto("/regie");
  await expect(page.getByText("Cet écran demande un accès régie.")).toBeVisible();
  // Aucune redirection vers une page de connexion : l'URL n'a pas changé.
  expect(new URL(page.url()).pathname).toBe("/regie");
});
