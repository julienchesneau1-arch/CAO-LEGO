import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import { forcerPeriode, reinitialiserContenus, reinitialiserFoyer } from "./reinitialiser";

/**
 * V4 — « Après ». Ce qui compte : l'invité sait jusqu'à quand ses données
 * vivent, il peut les emporter, et l'archive ne contient rien qu'il n'aurait
 * pas déjà le droit de voir.
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

const unzipDisponible = (): boolean => {
  try {
    execFileSync("unzip", ["-v"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
};

/** Donne l'accord de partage puis envoie une photo dessinée au passage. */
async function envoyerUnSouvenir(page: Page): Promise<void> {
  await page.goto("/photos/envoyer");
  const accepte = page.waitForResponse((r) => r.url().includes("/photos/consentement"));
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await accepte;

  const octets = await page.evaluate(async () => {
    const toile = document.createElement("canvas");
    toile.width = 48;
    toile.height = 48;
    const contexte = toile.getContext("2d");
    if (contexte === null) throw new Error("pas de contexte");
    contexte.fillStyle = "#7d2a3a";
    contexte.fillRect(0, 0, 48, 48);
    const blob = await new Promise<Blob | null>((r) => toile.toBlob(r, "image/jpeg", 0.9));
    return [...new Uint8Array(await (blob as Blob).arrayBuffer())];
  });
  await page.setInputFiles('input[type="file"]', {
    name: "souvenir.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from(octets),
  });

  for (let essai = 0; essai < 60; essai += 1) {
    if ((await enBase("select 1 from public.media")).length > 0) return;
    await page.waitForTimeout(250);
  }
  throw new Error("Le souvenir n'est jamais arrivé en base.");
}

test.beforeEach(async () => {
  await reinitialiserFoyer();
  await reinitialiserContenus();
  await forcerPeriode(null);
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query("delete from public.media_takedown");
  await client.query("delete from public.media_signal");
  await client.query("delete from public.media");
  await client.query("delete from public.media_consent");
  await client.query("delete from public.absent_messages");
  await client.end();
});

test.afterEach(async () => {
  await forcerPeriode(null);
});

test("après le mariage, l'accueil devient « Merci » et dit jusqu'à quand", async ({ page }) => {
  await forcerPeriode("apres");
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  await expect(page.getByRole("heading", { name: "Merci", exact: true })).toBeVisible();
  // Le mot des mariés n'est pas écrit : l'écran le dit au lieu de mentir.
  await expect(
    page.getByText("Julien et Lauriane écriront un mot ici après le mariage."),
  ).toBeVisible();

  // Les dates de fin, en clair. Le mariage est le 3 juin 2028.
  await expect(page.getByText(/Votre invitation reste ouverte jusqu’au 3 septembre 2028/)).toBeVisible();
  await expect(page.getByText(/supprimées le 3 juin 2029/)).toBeVisible();
});

test("le mot des mariés s'écrit depuis l'admin et s'affiche aussitôt", async ({ page, browser }) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/contenus?section=infos&element=apres.merci");
  await maries.locator('textarea[name="texte_fr"]').fill("Merci d’avoir été là. Vraiment.");
  await maries.locator('textarea[name="texte_en"]').fill("Thank you for being there. Truly.");
  const enregistre = maries.waitForResponse((r) => r.request().method() === "POST");
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await enregistre;
  await maries.context().close();

  await forcerPeriode("apres");
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await expect(page.getByText("Merci d’avoir été là. Vraiment.")).toBeVisible();
});

test("« Mes données » compte ce que nous détenons, sans le recopier", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await envoyerUnSouvenir(page);

  await page.goto("/mes-donnees");
  await expect(page.getByRole("heading", { name: "Mes données" })).toBeVisible();

  const invites = page.getByText("Personnes de votre foyer").locator("xpath=following-sibling::dd[1]");
  await expect(invites).toHaveText("1");
  const souvenirs = page.getByText("Souvenirs envoyés").locator("xpath=following-sibling::dd[1]");
  await expect(souvenirs).toHaveText("1");

  // Les échéances, avec leurs vraies dates. « 3 juin 2029 » vaut pour les
  // souvenirs comme pour les vœux : on cible la liste des échéances.
  const echeances = page.getByRole("region", { name: "Les suppressions automatiques" });
  await expect(echeances.getByText("3 juin 2029").first()).toBeVisible();
  await expect(
    page.getByText(/Pour corriger ou supprimer quelque chose, appelez-nous/),
  ).toBeVisible();
});

test("le livre d'or ne montre que les messages rendus publics", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  // Un mot privé, laissé depuis l'écran « Ceux qui sont loin ».
  await page.goto("/loin");
  await page.locator('textarea[name="message"]').fill("Un mot gardé pour vous deux.");
  const prive = page.waitForResponse((r) => r.request().method() === "POST");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await prive;
  // La redirection du formulaire est encore en vol : partir maintenant
  // annulerait la navigation suivante.
  await page.waitForLoadState("networkidle");

  // Un mot public, posé directement pour ne pas dépendre de l'écran.
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  await client.query(
    `insert into public.absent_messages (body, visibility) values ($1, 'guestbook')`,
    ["Nous pensons à vous très fort."],
  );
  await client.end();

  await page.goto("/messages");
  await expect(page.getByText("Nous pensons à vous très fort.")).toBeVisible();
  await expect(page.getByText("Un mot gardé pour vous deux.")).toHaveCount(0);
});

test("les photos du photographe vivent dans leur section, fermée sans invitation", async ({
  page,
  browser,
}) => {
  const maries = await ouvrirAdmin(browser);
  await maries.goto("/admin/photographe");
  await expect(maries.getByText("Aucune photo du photographe pour l’instant.")).toBeVisible();

  const octets = await maries.evaluate(async () => {
    const toile = document.createElement("canvas");
    toile.width = 40;
    toile.height = 40;
    toile.getContext("2d")!.fillRect(0, 0, 40, 40);
    const blob = await new Promise<Blob | null>((r) => toile.toBlob(r, "image/jpeg", 0.9));
    return [...new Uint8Array(await (blob as Blob).arrayBuffer())];
  });
  await maries.setInputFiles('input[name="fichiers"]', {
    name: "photographe-01.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from(octets),
  });
  const depose = maries.waitForResponse((r) => r.url().includes("/admin/photographe/televerser"));
  await maries.getByRole("button", { name: "Enregistrer" }).click();
  await depose;
  await expect(maries.getByText("1 photo(s) ajoutée(s).")).toBeVisible();
  await maries.context().close();

  const [ligne] = await enBase<{ id: string; source: string; household_id: string | null }>(
    "select id, source, household_id from public.media",
  );
  expect(ligne?.source).toBe("photographe");
  // Elle n'appartient à aucun foyer : rien ne doit laisser croire le contraire.
  expect(ligne?.household_id).toBeNull();

  // Visible dans sa section pour un invité reconnu…
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/photographe");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toBeVisible();

  // …et absente de la galerie des souvenirs, qui reste celle des invités.
  await page.goto("/photos");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toHaveCount(0);

  // Fermée à qui n'a pas d'invitation.
  const inconnu = await browser.newContext({ baseURL: "http://127.0.0.1:3220" });
  const pageInconnu = await inconnu.newPage();
  await pageInconnu.goto("/photographe");
  await expect(
    pageInconnu.getByText("Ces photos ne sont visibles que depuis une invitation."),
  ).toBeVisible();
  await inconnu.close();
});

test.skip(!unzipDisponible(), "unzip absent : l'archive ne peut pas être relue");
test("l'archive ZIP s'ouvre et ne contient que ce que l'invité peut voir", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await envoyerUnSouvenir(page);

  const reponse = await page.request.get("/photos/archive", {
    headers: {
      cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join("; "),
    },
  });
  expect(reponse.status()).toBe(200);
  expect(reponse.headers()["content-type"]).toContain("application/zip");
  // Jamais mise en cache : une photo retirée entre-temps ne doit pas y rester.
  expect(reponse.headers()["cache-control"]).toContain("no-store");

  const octets = await reponse.body();
  expect(octets.subarray(0, 2).toString("latin1")).toBe("PK");

  const dossier = mkdtempSync(join(tmpdir(), "jl-archive-"));
  try {
    const chemin = join(dossier, "archive.zip");
    writeFileSync(chemin, octets);
    // C'est `unzip` qui juge : il vérifie chaque CRC.
    expect(execFileSync("unzip", ["-t", chemin], { encoding: "utf8" })).toContain(
      "No errors detected",
    );
    const liste = execFileSync("unzip", ["-l", chemin], { encoding: "utf8" });
    expect(liste).toContain("souvenirs-du-mariage/");
    expect(liste).toContain(".jpg");
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("une photo masquée disparaît de l'archive dès la demande suivante", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await envoyerUnSouvenir(page);
  const [ligne] = await enBase<{ id: string }>("select id from public.media");

  const entete = {
    cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join("; "),
  };
  const avant = await (await page.request.get("/photos/archive", { headers: entete })).body();

  await page.goto(`/photos/${ligne!.id}`);
  const retire = page.waitForResponse((r) => r.url().includes("/photos/retrait"));
  await page.getByRole("button", { name: "Masquer cette photo" }).click();
  await retire;

  const apres = await (await page.request.get("/photos/archive", { headers: entete })).body();
  // L'archive vide fait 22 octets : la photo n'y est plus.
  expect(apres.byteLength).toBeLessThan(avant.byteLength);
  expect(apres.byteLength).toBe(22);
});
