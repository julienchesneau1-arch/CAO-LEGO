import { expect, test } from "@playwright/test";
import { reinitialiserFoyer } from "./reinitialiser";
import { FOYER } from "./fixtures";

/**
 * Parcours obligatoires du brief §12, partie « accès ».
 * Chacun compte ses gestes : l'objectif du brief est trois taps pour toute
 * information essentielle, quatre pour répondre.
 */

test.beforeEach(async () => {
  await reinitialiserFoyer();
});

test("QR du foyer : l'invité est reconnu, premier lancement passable", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);

  // Écran 1 : ouverture signature, « Passer » visible immédiatement.
  const passer = page.getByRole("button", { name: "Passer" });
  await expect(passer).toBeVisible();

  // Un seul geste suffit à atteindre l'accueil.
  await passer.click();
  await expect(page.getByText(`Bienvenue, ${FOYER.label}.`)).toBeVisible();
  await expect(page.getByRole("link", { name: "Répondre" })).toBeVisible();
});

test("premier lancement : trois écrans, puis plus jamais", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Continuer" }).click();
  await expect(page.getByText("Confort de lecture")).toBeVisible();
  await page.getByRole("button", { name: "Continuer" }).click();
  await expect(page.getByText("Tout est ici.").first()).toBeVisible();
  await page.getByRole("button", { name: "Tout est ici." }).click();

  await page.reload();
  await expect(page.getByRole("button", { name: "Passer" })).toHaveCount(0);
});

test("la page ne défile pas derrière l'ouverture", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).toBe("hidden");
  await page.getByRole("button", { name: "Passer" }).click();
  expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).not.toBe("hidden");
});

test("code de secours : échec discret, puis succès", async ({ page }) => {
  await page.goto("/retrouver");
  await page.getByLabel("Votre nom").fill("Personne");
  await page.getByLabel("Code à six caractères").fill("XXXXXX");
  await page.getByRole("button", { name: "Retrouver" }).click();
  // Message unique : il ne dit jamais lequel des deux champs a échoué.
  await expect(page.locator('p[role="alert"]')).toContainText(
    "Nous ne trouvons pas cette invitation",
  );

  await page.getByLabel("Votre nom").fill(FOYER.invite);
  await page.getByLabel("Code à six caractères").fill(FOYER.code.toLowerCase());
  await page.getByRole("button", { name: "Retrouver" }).click();
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText(`Bienvenue, ${FOYER.label}.`)).toBeVisible();
});

test("partage de l'accès : un proche ouvre la même invitation", async ({ page, browser }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.getByRole("link", { name: "Partager l’accès au foyer" }).click();
  await page.getByRole("button", { name: "Créer un lien" }).click();

  const lien = await page.locator("code").innerText();
  expect(lien).toContain("/p/");

  // Le téléphone du proche : aucun cookie, il suit seulement le lien.
  const proche = await browser.newContext({ baseURL: page.url() });
  const pageProche = await proche.newPage();
  await pageProche.goto(new URL(lien).pathname);
  await pageProche.getByRole("button", { name: "Passer" }).click();
  await expect(pageProche.getByText(`Bienvenue, ${FOYER.label}.`)).toBeVisible();
  await proche.close();
});

test("confort de lecture « très grande » : aucun débordement", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.evaluate(() =>
    localStorage.setItem(
      "jl_confort",
      JSON.stringify({ taille: "tres-grande", papier: "non", mouvement: "normal" }),
    ),
  );
  for (const chemin of ["/", "/retrouver", "/design"]) {
    await page.goto(chemin);
    const deborde = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(deborde, `débordement horizontal sur ${chemin}`).toBe(false);
  }
});

test("les cibles tactiles font au moins 48 px", async ({ page }) => {
  await page.goto("/retrouver");
  for (const nom of ["Retrouver"]) {
    const boite = await page.getByRole("button", { name: nom }).boundingBox();
    expect(boite?.height ?? 0).toBeGreaterThanOrEqual(48);
  }
  const champ = await page.getByLabel("Votre nom").boundingBox();
  expect(champ?.height ?? 0).toBeGreaterThanOrEqual(48);
});

test("QR générique : accès sans donnée nominative", async ({ page }) => {
  await page.goto("/g");
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText("Bienvenue.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Partager l’accès au foyer" })).toHaveCount(0);
});
