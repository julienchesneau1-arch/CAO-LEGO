import { expect, test } from "@playwright/test";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import { reinitialiserContenus, reinitialiserFoyer } from "./reinitialiser";

/**
 * Défis photo (brief §8.7, bonus) et indicateurs de réussite (§16).
 *
 * Les deux touchent au §17 : aucun compteur de participation nulle part chez
 * l'invité, et aucun indicateur approché quand il n'est pas mesurable sans
 * traceur.
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
  await client.query("delete from public.media_takedown");
  await client.query("delete from public.media_signal");
  await client.query("delete from public.media");
  await client.query("delete from public.media_consent");
  await client.query("delete from public.emails");
  await client.query(
    `update public.photo_challenges
        set title_fr = '[À COMPLÉTER]', title_en = '[TO BE COMPLETED]', published = false`,
  );
  await client.query("update public.households set first_opened_at = null");
  await client.end();
});

test("un défi sans intitulé n'apparaît nulle part, même publié", async ({ page, browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/defis");
  await expect(maries.getByText(/Aucun classement, aucun compteur/)).toBeVisible();

  // Publié, mais l'intitulé reste « [À COMPLÉTER] ».
  const premier = maries.locator('form[action="/admin/defis/enregistrer"]').first();
  await premier.getByLabel("Visible des invités").check();
  const publie = maries.waitForResponse((r) => r.request().method() === "POST");
  await premier.getByRole("button", { name: "Enregistrer" }).click();
  await publie;
  await maries.context().close();

  // Côté invité : aucune trace, et surtout pas le texte d'attente.
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/photos/envoyer");
  const accepte = page.waitForResponse((r) => r.url().includes("/photos/consentement"));
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await accepte;
  await expect(page.getByText("[À COMPLÉTER]")).toHaveCount(0);
  await expect(page.getByLabel("Les défis")).toHaveCount(0);
});

test("un défi écrit et publié se choisit à l'envoi, et rien n'est compté", async ({
  page,
  browser,
}) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/defis");
  const premier = maries.locator('form[action="/admin/defis/enregistrer"]').first();
  await premier.locator('input[name="title_fr"]').fill("Une main dans une autre");
  await premier.locator('input[name="title_en"]').fill("A hand in another");
  await premier.getByLabel("Visible des invités").check();
  const publie = maries.waitForResponse((r) => r.request().method() === "POST");
  await premier.getByRole("button", { name: "Enregistrer" }).click();
  await publie;
  await maries.context().close();

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/photos/envoyer");
  const accepte = page.waitForResponse((r) => r.url().includes("/photos/consentement"));
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await accepte;

  const choix = page.getByLabel("Les défis");
  await expect(choix).toBeVisible();
  await choix.selectOption({ label: "Une main dans une autre" });

  const octets = await page.evaluate(async () => {
    const toile = document.createElement("canvas");
    toile.width = 40;
    toile.height = 40;
    toile.getContext("2d")!.fillRect(0, 0, 40, 40);
    const blob = await new Promise<Blob | null>((r) => toile.toBlob(r, "image/jpeg", 0.9));
    return [...new Uint8Array(await (blob as Blob).arrayBuffer())];
  });
  await page.setInputFiles('input[type="file"]', {
    name: "defi.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from(octets),
  });

  for (let essai = 0; essai < 60; essai += 1) {
    if ((await enBase("select 1 from public.media")).length > 0) break;
    await page.waitForTimeout(250);
  }
  const [ligne] = await enBase<{ challenge_id: string | null }>(
    "select challenge_id from public.media",
  );
  expect(ligne?.challenge_id).not.toBeNull();

  // Nulle part un nombre de réponses : le §17 interdit le compteur.
  await page.goto("/photos");
  await expect(page.getByText(/\d+\s+(réponse|participant)/i)).toHaveCount(0);
});

test("les indicateurs mesurent sans traceur, et disent ce qu'ils ne mesurent pas", async ({
  page,
  browser,
}) => {
  // Une ouverture et une réponse, pour avoir quelque chose à mesurer.
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/reponse");
  const repondu = page.waitForResponse((r) => r.url().includes("/reponse/statut"));
  await page.getByRole("button", { name: "Oui", exact: true }).click();
  await repondu;

  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/indicateurs");

  await expect(maries.getByRole("heading", { name: "Les indicateurs" })).toBeVisible();
  await expect(maries.getByText("Foyers ayant ouvert leur invitation")).toBeVisible();
  // Un foyer, ouvert et répondu : 100 % des deux.
  await expect(maries.getByText("100%").first()).toBeVisible();
  await expect(maries.getByText("Atteint").first()).toBeVisible();

  // Les quatre indicateurs non mesurables figurent, avec leur raison.
  for (const libelle of [
    "Envois de souvenirs définitivement échoués",
    "Questions reçues par téléphone ou message",
    "Interventions de Julien et Lauriane le jour J",
    "Incident bloquant le jour J",
  ]) {
    await expect(maries.getByText(libelle)).toBeVisible();
  }
  await expect(maries.getByText("Non mesurable").first()).toBeVisible();
  await expect(maries.getByText(/Le brief l’interdit/)).toBeVisible();

  // Le délai médian est mesuré, pas approché.
  await expect(maries.getByText("Délai médian entre l’ouverture et la réponse")).toBeVisible();
  await maries.context().close();
});

test("aucun indicateur n'est visible d'un invité", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  // L'écran des indicateurs est derrière le garde de l'admin.
  await page.goto("/admin/indicateurs");
  await expect(page.getByText("Cet espace demande un lien d’accès valide.")).toBeVisible();
  await expect(page.getByText("Foyers ayant ouvert leur invitation")).toHaveCount(0);
});
