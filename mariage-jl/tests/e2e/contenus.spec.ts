import { expect, test } from "@playwright/test";
import { BASE_URL, FOYER } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import { reinitialiserContenus, reinitialiserFoyer } from "./reinitialiser";

/**
 * Espace « Contenus » : ce que les mariés écrivent arrive bien chez l'invité.
 * Chaque parcours part d'une base remise à « [À COMPLÉTER] », écrit une seule
 * chose, et la relit du côté invité — c'est le seul moyen de vérifier que
 * plus rien ne dépend d'une migration SQL.
 */
test.beforeEach(async () => {
  await reinitialiserFoyer();
  await reinitialiserContenus();
});

test("un horaire saisi remplace « Horaire à confirmer » sur le programme", async ({
  page,
  browser,
}) => {
  await page.goto("/programme");
  await expect(page.getByText("Horaire à confirmer").first()).toBeVisible();

  const maries = await ouvrirAdmin(browser);
  // On passe par la liste, comme les mariés : elle annonce l'état de chacun.
  await maries.goto("/admin/contenus?section=moments");
  await expect(maries.getByText("À compléter").first()).toBeVisible();
  await maries.getByRole("link", { name: /L’Horizon/ }).click();

  await maries.locator('input[name="debut"]').fill("15:30");
  await maries.locator('input[name="fin"]').fill("16:15");
  await maries.locator('input[name="place"]').fill("La chapelle du domaine");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await expect(maries.getByText("Enregistré.")).toBeVisible();

  // La liste reflète immédiatement l'horaire enregistré.
  await expect(maries.getByRole("link", { name: /L’Horizon/ })).toContainText("15:30");
  await maries.context().close();

  await page.goto("/programme");
  await expect(page.getByText("de 15:30 à 16:15")).toBeVisible();
  await expect(page.getByText("La chapelle du domaine")).toBeVisible();
});

test("un bloc d'infos écrit dans les deux langues s'affiche dans les deux langues", async ({
  page,
  browser,
}) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=infos&element=infos.tenue");
  await maries
    .locator('textarea[name="texte_fr"]')
    .fill("Tenue de ville, chaussures plates bienvenues.");
  await maries.locator('textarea[name="texte_en"]').fill("Smart casual, flat shoes welcome.");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;

  // De retour sur la liste, le bloc est marqué « Écrit ».
  await expect(maries.getByRole("link", { name: /La tenue/ })).toContainText("Écrit");
  await maries.context().close();

  await page.goto("/infos");
  await expect(page.getByText("Tenue de ville, chaussures plates bienvenues.")).toBeVisible();

  await page.context().addCookies([{ name: "jl_langue", value: "en", url: BASE_URL }]);
  await page.goto("/infos");
  await expect(page.getByText("Smart casual, flat shoes welcome.")).toBeVisible();
});

test("une réponse de FAQ écrite par les mariés apparaît chez l'invité", async ({
  page,
  browser,
}) => {
  await page.goto("/faq");
  await expect(
    page.getByText("La réponse sera écrite ici avant le faire-part.").first(),
  ).toBeVisible();

  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=faq");
  await maries.getByRole("link", { name: /À quelle heure arriver/ }).click();
  await maries.locator('textarea[name="answer_fr"]').fill("Dès 14 h, jusqu’au bout de la nuit.");
  await maries
    .locator('textarea[name="answer_en"]')
    .fill("From 2 pm until the end of the night.");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await maries.context().close();

  await page.goto("/faq");
  await expect(page.getByText("Dès 14 h, jusqu’au bout de la nuit.")).toBeVisible();
});

test("une question dépubliée disparaît de la FAQ des invités", async ({ page, browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=faq");
  await maries.getByRole("link", { name: /Y a-t-il une liste de mariage/ }).click();
  await maries.getByLabel("Visible des invités").uncheck();
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await expect(
    maries.getByRole("link", { name: /Y a-t-il une liste de mariage/ }),
  ).toContainText("Masquée aux invités");
  await maries.context().close();

  await page.goto("/faq");
  await expect(page.getByText("Y a-t-il une liste de mariage")).toHaveCount(0);
});

test("un hébergement ajouté apparaît dans « Dormir »", async ({ page, browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=hebergements");
  await expect(maries.getByText("Aucun hébergement pour l’instant.")).toBeVisible();
  await maries.getByRole("link", { name: "Ajouter un hébergement" }).click();

  await maries.locator('input[name="name"]').fill("Le Relais du Domaine");
  await maries.locator('input[name="distance_km"]').fill("3,5");
  await maries.locator('input[name="price_hint"]').fill("90 € la nuit");
  await maries.locator('input[name="shuttle"]').check();
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Ajouter" }).click();
  await enregistre;
  await expect(maries.getByRole("link", { name: /Le Relais du Domaine/ })).toContainText("3.5 km");
  await maries.context().close();

  await page.goto("/infos");
  await expect(page.getByText("Le Relais du Domaine")).toBeVisible();
  await expect(page.getByText("3.5 km du domaine")).toBeVisible();
  await expect(page.getByText("Navette depuis cet hébergement")).toBeVisible();
});

test("la date limite saisie devient l'échéance affichée sur l'accueil", async ({
  page,
  browser,
}) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=journee");
  await maries.locator('input[name="date_limite"]').fill("2028-04-15");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  // L'écran redit la date en clair, pour qu'un 15/04 ne soit pas lu 4 avril.
  await expect(maries.getByText("15 avril 2028")).toBeVisible();
  await maries.context().close();

  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText(/15 avril 2028/)).toBeVisible();
});

/**
 * Un lien saisi par les mariés finit dans un `href` vu par tous les invités.
 * La validation du navigateur ne suffit pas : on la neutralise exprès — comme
 * le ferait un formulaire rejoué ou bricolé — et on vérifie que c'est le
 * serveur qui refuse.
 */
test("un lien qui n'est pas http est refusé par le serveur", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=infos&element=infos.liste_mariage");
  await maries.locator('textarea[name="texte_fr"]').fill("Chez notre caviste.");
  await maries.locator('textarea[name="texte_en"]').fill("At our wine merchant.");
  await maries.locator('input[name="lien"]').evaluate((champ: HTMLInputElement) => {
    champ.type = "text";
    champ.form?.setAttribute("novalidate", "novalidate");
  });
  await maries.locator('input[name="lien"]').fill("javascript:alert(1)");

  const refus = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await refus;

  await expect(maries.getByText("Ce lien n’est pas une adresse http ou https.")).toBeVisible();

  // Rien n'a été enregistré : le bloc est intact, lien comme textes.
  await maries.goto("/admin/contenus?section=infos&element=infos.liste_mariage");
  await expect(maries.locator('input[name="lien"]')).toHaveValue("");
  await expect(maries.locator('textarea[name="texte_fr"]')).toHaveValue("[À COMPLÉTER]");
  await maries.context().close();
});

test("le compteur « à compléter » diminue à chaque contenu écrit", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=infos");
  const avant = Number(
    /(\d+) à compléter/.exec((await maries.locator("main").innerText()) ?? "")?.[1] ?? "0",
  );
  expect(avant).toBeGreaterThan(0);

  await maries.goto("/admin/contenus?section=infos&element=infos.venir");
  await maries.locator('textarea[name="texte_fr"]').fill("Par la D147, puis l’allée de tilleuls.");
  await maries.locator('textarea[name="texte_en"]').fill("Via the D147, then the lime avenue.");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;

  await expect(maries.getByText(`${avant - 1} à compléter.`)).toBeVisible();
  await maries.context().close();
});

test("le journal d'audit garde la trace sans enregistrer d'adresse", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=journee");
  await maries.locator('input[name="date_limite"]').fill("2028-04-15");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await maries.context().close();

  const { Client } = await import("pg");
  const { URL_E2E } = await import("./fixtures");
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    const { rows } = await client.query<{ action: string; target: string }>(
      "select action, target from public.audit_log",
    );
    expect(rows.map((r) => r.action)).toContain("date_limite.maj");
    for (const ligne of rows) expect(ligne.target).not.toContain("@");
  } finally {
    await client.end();
  }
});
