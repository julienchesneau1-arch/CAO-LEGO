import { expect, test, type Page } from "@playwright/test";
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";
import { DOSSIER_MEDIAS, FOYER, URL_E2E } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import {
  forcerPeriode,
  poserJourneeAutourDeMaintenant,
  reinitialiserContenus,
  reinitialiserFoyer,
} from "./reinitialiser";

/**
 * V3 — photos et vidéos. Les parcours qui comptent sont ceux qui vérifient
 * une **promesse** : pas d'envoi sans accord, pas de position GPS sur le
 * disque, un retrait qui masque tout de suite, et un souvenir confié aux
 * mariés qui ne se télécharge pas avec un simple identifiant.
 */
const enBase = async <T extends Record<string, unknown>>(
  sql: string,
  valeurs: ReadonlyArray<unknown> = [],
): Promise<T[]> => {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    return (await client.query<T>(sql, valeurs as unknown[])).rows;
  } finally {
    await client.end();
  }
};

/**
 * Fabrique une vraie photo dans le navigateur — un dessin sur un canvas,
 * encodé en JPEG — puis y injecte un segment APP1 « Exif » contenant une
 * position. C'est le seul moyen honnête de vérifier que le serveur retire la
 * position d'un fichier qui en contient réellement une.
 */
async function choisirPhotoGeolocalisee(page: Page, nom = "souvenir.jpg"): Promise<void> {
  const octets = await page.evaluate(async () => {
    const toile = document.createElement("canvas");
    toile.width = 64;
    toile.height = 48;
    const contexte = toile.getContext("2d");
    if (contexte === null) throw new Error("pas de contexte");
    contexte.fillStyle = "#c8452a";
    contexte.fillRect(0, 0, 64, 48);
    contexte.fillStyle = "#f2e8d5";
    contexte.fillRect(8, 8, 24, 24);

    const blob = await new Promise<Blob | null>((resoudre) =>
      toile.toBlob(resoudre, "image/jpeg", 0.9),
    );
    if (blob === null) throw new Error("pas de blob");
    const base = new Uint8Array(await blob.arrayBuffer());

    // Injection d'un APP1 « Exif » juste après le marqueur de début.
    const exif = ["Exif", String.fromCharCode(0, 0), "GPSLatitude47.1234GPSLongitude0.4321"].join(
      "",
    );
    const charge = new Uint8Array(exif.length);
    for (let i = 0; i < exif.length; i += 1) charge[i] = exif.charCodeAt(i);
    const taille = charge.length + 2;
    const sortie = new Uint8Array(base.length + 4 + charge.length);
    sortie.set(base.subarray(0, 2), 0);
    sortie.set([0xff, 0xe1, (taille >> 8) & 0xff, taille & 0xff], 2);
    sortie.set(charge, 6);
    sortie.set(base.subarray(2), 6 + charge.length);
    return [...sortie];
  });

  await page.setInputFiles('input[type="file"]', {
    name: nom,
    mimeType: "image/jpeg",
    buffer: Buffer.from(octets),
  });
}

/** Attend qu'un média soit en base, sans dormir à l'aveugle. */
async function attendreMedias(combien: number): Promise<void> {
  for (let essai = 0; essai < 60; essai += 1) {
    const lignes = await enBase<{ n: number }>("select count(*)::int as n from public.media");
    if (Number(lignes[0]?.n) >= combien) return;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Moins de ${combien} média(s) en base après 15 s.`);
}

/**
 * Le fichier existe-t-il toujours sur le disque ? On ne compte pas le
 * dossier entier : il garde les envois des parcours précédents de la série,
 * et ce n'est pas ce qu'on vérifie ici.
 */
const surLeDisque = (chemin: string): boolean => {
  try {
    return statSync(join(DOSSIER_MEDIAS, chemin)).isFile();
  } catch {
    return false;
  }
};

/** Ouvre l'invitation, franchit l'accueil, et donne l'accord de partage. */
async function preparerPartage(page: Page, visibilite: "invites" | "maries" = "invites"): Promise<void> {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/photos/envoyer");
  if (visibilite === "maries") {
    await page.getByLabel("Visibles des mariés seulement").check();
  }
  const accepte = page.waitForResponse((r) => r.url().includes("/photos/consentement"));
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await accepte;
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
  await client.query(
    "update public.parametres set photos_en_pause = false, ceremonie_debranchee = true",
  );
  await client.end();
});

test.afterEach(async () => {
  await forcerPeriode(null);
});

test("aucun envoi n'est possible avant d'avoir donné son accord", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await page.goto("/photos/envoyer");

  // Pas de sélecteur de fichier tant que l'accord n'est pas donné.
  await expect(page.getByRole("heading", { name: "Avant le premier envoi" })).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);

  const accepte = page.waitForResponse((r) => r.url().includes("/photos/consentement"));
  await page.getByRole("button", { name: "J’accepte de partager" }).click();
  await accepte;

  await expect(page.getByText("Vos souvenirs sont visibles des invités.")).toBeVisible();
  await expect(page.locator('input[type="file"]')).toBeVisible();

  const accords = await enBase<{ consent_text_version: string; visibilite: string }>(
    "select consent_text_version, visibilite from public.media_consent",
  );
  expect(accords).toHaveLength(1);
  expect(accords[0]?.visibilite).toBe("invites");
});

test("une photo géolocalisée arrive sur le disque sans sa position, et reste lisible", async ({
  page,
}) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);

  const [ligne] = await enBase<{
    id: string;
    storage_path: string;
    gps_stripped: boolean;
    mime: string;
  }>("select id, storage_path, gps_stripped, mime from public.media");
  expect(ligne).toBeDefined();
  expect(ligne?.gps_stripped).toBe(true);

  // Ce qui est réellement écrit sur le disque, octet par octet.
  const surDisque = readFileSync(join(DOSSIER_MEDIAS, ligne!.storage_path));
  expect(surDisque.includes(Buffer.from("GPSLatitude"))).toBe(false);
  expect(surDisque.includes(Buffer.from("Exif"))).toBe(false);

  // Et le fichier servi est toujours une image décodable par le navigateur.
  const dimensions = await page.evaluate(async (id) => {
    const reponse = await fetch(`/m/${id}`);
    const image = await createImageBitmap(await reponse.blob());
    return { largeur: image.width, hauteur: image.height };
  }, ligne!.id);
  expect(dimensions.largeur).toBe(64);
  expect(dimensions.hauteur).toBe(48);

  // Elle apparaît dans la galerie, et dans « Mes souvenirs ».
  await page.goto("/photos");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toBeVisible();
  await page.goto("/photos?mes=1");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toBeVisible();
});

test("un souvenir n'est pas servi sans invitation reconnue", async ({ page, browser }) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string }>("select id from public.media");

  // Un visiteur sans cookie de foyer : l'identifiant ne suffit pas.
  const inconnu = await browser.newContext();
  const reponse = await inconnu.request.get(`http://127.0.0.1:3220/m/${ligne!.id}`);
  expect(reponse.status()).toBe(404);
  await inconnu.close();
});

test("une demande de retrait masque la photo tout de suite, pour tout le monde", async ({
  page,
}) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string; storage_path: string }>(
    "select id, storage_path from public.media",
  );

  await page.goto(`/photos/${ligne!.id}`);
  const retire = page.waitForResponse((r) => r.url().includes("/photos/retrait"));
  await page.getByRole("button", { name: "Masquer cette photo" }).click();
  await retire;

  await expect(page.getByText("C’est masqué. Merci de nous l’avoir dit.")).toBeVisible();
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toHaveCount(0);

  // Masquée en base, et le fichier n'est plus servi — même au foyer d'origine.
  const [apres] = await enBase<{ status: string }>("select status from public.media");
  expect(apres?.status).toBe("hidden");
  expect((await page.request.get(`/m/${ligne!.id}`)).status()).toBe(404);

  // Le fichier est toujours sur le disque : la décision se défait.
  expect(surLeDisque(ligne!.storage_path)).toBe(true);
});

test("la régie voit le signalement, peut rendre visible puis classer", async ({
  page,
  browser,
}) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string }>("select id from public.media");

  await page.goto(`/photos/${ligne!.id}`);
  await page.locator('textarea[name="raison"]').fill("J’apparais dessus.");
  const retire = page.waitForResponse((r) => r.url().includes("/photos/retrait"));
  await page.getByRole("button", { name: "Masquer cette photo" }).click();
  await retire;

  const regie = await ouvrirAdmin(browser);
  await regie.goto("/regie");
  await expect(regie.getByText("J’apparais dessus.")).toBeVisible();
  await expect(regie.getByText("Masqué")).toBeVisible();

  const rend = regie.waitForResponse((r) => r.url().includes("/regie/medias"));
  await regie.getByRole("button", { name: "Rendre visible" }).click();
  await rend;
  expect((await enBase<{ status: string }>("select status from public.media"))[0]?.status).toBe(
    "published",
  );

  const classe = regie.waitForResponse((r) => r.url().includes("/regie/medias"));
  await regie.getByRole("button", { name: "Classer ce signalement" }).click();
  await classe;
  const [signalement] = await enBase<{ resolved_at: Date | null }>(
    "select resolved_at from public.media_takedown",
  );
  expect(signalement?.resolved_at).not.toBeNull();
  await regie.context().close();
});

test("un souvenir confié aux mariés n'apparaît pas dans la galerie des autres", async ({
  page,
  browser,
}) => {
  await preparerPartage(page, "maries");
  await expect(page.getByText("Vos souvenirs sont visibles des mariés seulement.")).toBeVisible();

  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string; visibilite: string }>(
    "select id, visibilite from public.media",
  );
  expect(ligne?.visibilite).toBe("maries");

  // Le foyer qui l'a envoyée le revoit, pour pouvoir le retirer.
  await page.goto("/photos");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toBeVisible();

  // Un autre foyer, non : ni dans la galerie, ni par son identifiant.
  const autre = await creerAutreFoyer();
  const contexte = await browser.newContext({ baseURL: "http://127.0.0.1:3220" });
  const pageAutre = await contexte.newPage();
  await pageAutre.goto(`/i/${autre}`);
  await pageAutre.getByRole("button", { name: "Passer" }).click();
  await pageAutre.goto("/photos");
  await expect(pageAutre.locator(`img[src="/m/${ligne!.id}"]`)).toHaveCount(0);
  expect((await pageAutre.request.get(`/m/${ligne!.id}`)).status()).toBe(404);
  await contexte.close();

  // Et le mur projeté ne le montre pas non plus.
  const mur = await page.request.get("/live/liste");
  expect(((await mur.json()) as { identifiants: string[] }).identifiants).not.toContain(ligne!.id);
});

test("pendant la cérémonie débranchée, l'envoi est refusé et rien n'est perdu", async ({
  page,
}) => {
  await preparerPartage(page);

  await poserJourneeAutourDeMaintenant("02");
  await page.reload();
  await expect(page.getByText(/L’envoi de souvenirs est suspendu/)).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);

  /*
    Un envoi rejoué malgré tout est refusé côté serveur, avec sa raison.
    Le cookie du foyer est passé à la main : l'API de requêtes de Playwright
    ne l'attache pas aux POST, alors qu'un vrai formulaire le ferait.
  */
  const cookies = await page.context().cookies();
  const entete = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  const refus = await page.request.post("/photos/televerser", {
    headers: { cookie: entete },
    multipart: {
      fichier: { name: "x.jpg", mimeType: "image/jpeg", buffer: Buffer.from([0xff, 0xd8]) },
    },
  });
  expect(refus.status()).toBe(409);
  expect(((await refus.json()) as { refus: string }).refus).toBe("envois_suspendus");
  expect(await enBase("select 1 from public.media")).toHaveLength(0);
});

test("le mur en direct montre les souvenirs, sans nom ni compteur", async ({ page }) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string }>("select id from public.media");

  await page.goto("/live");
  await expect(page.locator(`img[src="/m/${ligne!.id}"]`)).toBeVisible();
  // Aucun nom de foyer, aucun nombre : un mur projeté n'apprend rien sur
  // qui a envoyé quoi.
  await expect(page.getByText(FOYER.label)).toHaveCount(0);
  await expect(page.getByText(/\d+\s+(souvenir|photo)/i)).toHaveCount(0);
});

test("« j'aime » se pose et se retire, sans jamais afficher de nombre", async ({ page }) => {
  await preparerPartage(page);
  await choisirPhotoGeolocalisee(page);
  await attendreMedias(1);
  const [ligne] = await enBase<{ id: string }>("select id from public.media");

  await page.goto(`/photos/${ligne!.id}`);
  const aime = page.waitForResponse((r) => r.url().includes("/photos/aimer"));
  await page.getByRole("button", { name: "J’aime" }).click();
  await aime;
  expect(await enBase("select 1 from public.media_signal")).toHaveLength(1);

  const retire = page.waitForResponse((r) => r.url().includes("/photos/aimer"));
  await page.getByRole("button", { name: "J’aime" }).click();
  await retire;
  expect(await enBase("select 1 from public.media_signal")).toHaveLength(0);

  // Nulle part un compteur (§17).
  await page.goto("/photos");
  await expect(page.getByText(/\d+\s+j’aime/i)).toHaveCount(0);
});

/** Deuxième foyer jetable, pour vérifier ce qu'un autre invité voit. */
async function creerAutreFoyer(): Promise<string> {
  const { createHash } = await import("node:crypto");
  const jeton = "autre2foyer3pour4les5photos67890a";
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    await client.query(
      `insert into public.households (label_public, token_sha256, backup_code_sha256)
       values ('Autre foyer', $1, $2)
       on conflict (token_sha256) do nothing`,
      [
        createHash("sha256").update(jeton).digest(),
        createHash("sha256").update(`${jeton}-code`).digest(),
      ],
    );
  } finally {
    await client.end();
  }
  return jeton;
}
