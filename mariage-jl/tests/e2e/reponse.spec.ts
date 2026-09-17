import { expect, test } from "@playwright/test";
import { reinitialiserFoyer } from "./reinitialiser";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";

/**
 * Parcours obligatoires du brief §12 : réponse en quatre taps, parcours
 * « Non », et la règle du consentement des allergies vérifiée en base.
 */

/**
 * Attend que le serveur ait **traité** l'envoi avant de lire la base.
 * Attendre l'inactivité réseau ne suffit pas : le formulaire est envoyé par
 * `fetch` (pour que la file d'attente puisse rattraper un échec), et la page
 * pouvait déjà être inactive au moment du clic.
 */
const envoyer = async (
  page: import("@playwright/test").Page,
  nom: string,
  action = "/reponse/",
): Promise<void> => {
  // On attend la réponse **de ce formulaire** : attendre n'importe quel POST
  // laissait passer celui de la file d'attente et la lecture en base partait
  // trop tôt.
  const traite = page.waitForResponse(
    (reponse) => reponse.request().method() === "POST" && reponse.url().includes(action),
  );
  await page.getByRole("button", { name: nom, exact: true }).click();
  await traite;
  await page.waitForLoadState("networkidle");
};

const enBase = async <T extends Record<string, unknown>>(sql: string): Promise<T[]> => {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    const r = await client.query<T>(sql);
    return r.rows;
  } finally {
    await client.end();
  }
};

test.beforeEach(async () => {
  await reinitialiserFoyer();
});

test("répondre oui tient en quatre taps", async ({ page }) => {
  let taps = 0;
  const taper = async (action: Promise<void>): Promise<void> => {
    taps += 1;
    await action;
  };

  await page.goto(`/i/${FOYER.jeton}`);
  await taper(page.getByRole("button", { name: "Passer" }).click());
  await taper(page.getByRole("link", { name: "Réponse" }).click());
  await taper(envoyer(page, "Oui"));
  await expect(page.getByText("C’est noté. Nous avons hâte.")).toBeVisible();
  await taper(envoyer(page, "Enregistrer"));

  expect(taps).toBeLessThanOrEqual(4);
  const reponses = await enBase<{ status: string }>("select status from public.rsvp");
  expect(reponses[0]?.status).toBe("yes");
});

test("parcours « Non » : bienveillant et sans rien demander", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/reponse");
  await envoyer(page, "Non");

  await expect(page.getByText("Vous nous manquerez. Nous penserons à vous.")).toBeVisible();
  // Aucune étape de menu, aucune présence à cocher.
  await expect(page.getByText("Qui vient, et à quels moments")).toHaveCount(0);
  await expect(page.locator("input[required], textarea[required]")).toHaveCount(0);

  await page.locator('textarea[name="message"]').fill("Nous serons avec vous de loin.");
  await envoyer(page, "Enregistrer");
  // Le texte revient dans le formulaire : la réponse est bien enregistrée.
  await expect(page.locator('textarea[name="message"]')).toHaveValue(/de loin/);
  const lignes = await enBase<{ message_to_couple: string }>(
    "select message_to_couple from public.rsvp",
  );
  expect(lignes[0]?.message_to_couple).toContain("de loin");
});

test("une allergie n'est pas conservée sans consentement explicite", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/reponse");
  await envoyer(page, "Oui");

  await page.locator('input[name^="allergies-"]').first().fill("arachides");
  await envoyer(page, "Enregistrer");
  expect(await enBase("select 1 from public.health_allergies")).toHaveLength(0);

  // Avec la case cochée, la donnée est acceptée.
  await page.locator('input[name^="allergies-"]').first().fill("arachides");
  await page.getByLabel(/J’accepte que ces allergies/).check();
  await envoyer(page, "Enregistrer");
  const lignes = await enBase<{ content: string }>("select content from public.health_allergies");
  expect(lignes[0]?.content).toBe("arachides");
});

test("le programme est à un tap, avec son fichier d'agenda", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.getByRole("link", { name: "Programme" }).click();

  await expect(page.getByRole("heading", { name: "Le programme" })).toBeVisible();
  for (const nom of ["L’Éclat", "L’Horizon", "La Rencontre", "L’Ivresse", "La Nuit"]) {
    await expect(page.getByText(nom, { exact: false }).first()).toBeVisible();
  }
  // Les horaires ne sont pas connus : l'écran le dit, il n'invente pas.
  await expect(page.getByText("Horaire à confirmer").first()).toBeVisible();

  const reponse = await page.request.get("/programme/agenda.ics");
  expect(reponse.headers()["content-type"]).toContain("text/calendar");
  const ics = await reponse.text();
  expect(ics).toContain("BEGIN:VCALENDAR");
  expect(ics).toContain("DTSTART;VALUE=DATE:20280603");
});

test("le déroulé d'un moment est à deux taps", async ({ page }) => {
  await page.goto("/programme");
  await page.getByRole("link", { name: "Le déroulé en détail" }).first().click();
  await expect(page.getByRole("heading", { name: "Le déroulé en détail" })).toBeVisible();
  await expect(page.getByText("Le déroulé sera écrit ici avant le faire-part.")).toBeVisible();
});

test("la FAQ cherche sans se soucier des accents", async ({ page }) => {
  await page.goto("/faq");
  await expect(page.getByText("18 questions")).toBeVisible();
  await page.getByLabel("Chercher une question").fill("fauteuil");
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(1);

  await page.getByLabel("Chercher une question").fill("acces");
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();

  await page.getByLabel("Chercher une question").fill("zzzz");
  await expect(page.getByText("Aucune question ne correspond")).toBeVisible();
});

test("les infos donnent l'itinéraire sans inventer l'adresse", async ({ page }) => {
  await page.goto("/infos");
  await expect(page.getByText("Domaine de Roiffé, 86120 Roiffé (Vienne)")).toBeVisible();
  for (const nom of ["Apple Plans", "Google Maps", "Waze"]) {
    await expect(page.getByRole("link", { name: nom })).toBeVisible();
  }
  await expect(
    page.getByText("Cette information sera écrite ici avant le faire-part.").first(),
  ).toBeVisible();
});
