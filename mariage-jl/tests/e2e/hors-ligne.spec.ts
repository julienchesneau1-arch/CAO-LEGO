import { spawn, type ChildProcess } from "node:child_process";
import { expect, test } from "@playwright/test";
import { Client } from "pg";
import { FOYER, URL_E2E } from "./fixtures";
import { reinitialiserFoyer } from "./reinitialiser";

/**
 * Hors ligne (brief §12 et règle 4 : « le domaine est à la campagne »).
 *
 * Ces parcours démarrent **leur propre serveur** et le coupent pour simuler
 * la perte du réseau. C'est la seule façon de mesurer quelque chose ici :
 * `context.setOffline()` met bien `navigator.onLine` à faux, mais Chromium
 * continue de joindre 127.0.0.1 — un test bâti dessus passerait sans rien
 * vérifier. Couper le serveur reproduit ce que vit l'invité : le téléphone se
 * croit connecté, et plus rien ne répond.
 */
const PORT = 3246;
const BASE = `http://127.0.0.1:${PORT}`;

let serveur: ChildProcess | undefined;

const enBase = async <T extends Record<string, unknown>>(sql: string): Promise<T[]> => {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    return (await client.query<T>(sql)).rows;
  } finally {
    await client.end();
  }
};

async function allumer(): Promise<void> {
  serveur = spawn("node", [".next/standalone/server.js"], {
    env: {
      ...process.env,
      PORT: String(PORT),
      HOSTNAME: "127.0.0.1",
      JL_DATABASE_URL: URL_E2E,
      JL_COOKIE_SECRET: "secret-des-parcours-hors-ligne-0123456789",
    },
    stdio: "ignore",
    detached: true,
  });
  for (let essai = 0; essai < 60; essai += 1) {
    try {
      if ((await fetch(`${BASE}/api/health`)).ok) return;
    } catch {
      /* démarrage */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error("Le serveur des parcours hors ligne n'a pas démarré.");
}

async function eteindre(): Promise<void> {
  if (serveur?.pid === undefined) return;
  try {
    process.kill(-serveur.pid, "SIGKILL");
  } catch {
    serveur.kill("SIGKILL");
  }
  serveur = undefined;
  for (let essai = 0; essai < 40; essai += 1) {
    try {
      await fetch(`${BASE}/api/health`);
    } catch {
      return; // plus personne ne répond : c'est ce qu'on veut
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("Le serveur des parcours hors ligne répond encore.");
}

/**
 * Attend que le service worker **contrôle** la page, et pas seulement qu'il
 * soit activé : entre les deux, une page se charge encore sans lui. C'est
 * aussi vrai pour un invité — la toute première ouverture n'est jamais mise
 * en cache, seule la suivante l'est.
 */
const attendreServiceWorker = async (page: import("@playwright/test").Page): Promise<void> => {
  await page.waitForFunction(
    async () => {
      const enregistrement = await navigator.serviceWorker?.getRegistration();
      return enregistrement?.active?.state === "activated" && navigator.serviceWorker.controller !== null;
    },
    undefined,
    { timeout: 20_000 },
  );
};

test.describe.configure({ mode: "serial" });

test.beforeEach(async () => {
  await reinitialiserFoyer();
  if (serveur === undefined) await allumer();
});

test.afterAll(async () => {
  await eteindre().catch(() => undefined);
});

test("le programme, les infos et la FAQ restent consultables sans réseau", async ({ page }) => {
  await page.goto(`${BASE}/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await attendreServiceWorker(page);
  // Une navigation de plus après la prise de contrôle : la toute première
  // n'est pas encore passée par le service worker, ni chez l'invité.
  await page.reload({ waitUntil: "networkidle" });

  // Ouverts une fois avec le réseau : c'est la condition posée par le brief.
  for (const chemin of ["/programme", "/infos", "/faq"]) {
    await page.goto(`${BASE}${chemin}`);
    await page.waitForLoadState("networkidle");
  }

  // Le cache ne contient que les trois pages de contenu, sans paramètre :
  // les charges RSC préchargées n'y entrent pas, sinon il grossirait sans fin.
  const cache = await page.evaluate(async () => {
    const chemins: string[] = [];
    for (const nom of await caches.keys()) {
      if (nom.includes("precache")) continue;
      for (const requete of await (await caches.open(nom)).keys()) {
        const url = new URL(requete.url);
        chemins.push(url.pathname + url.search);
      }
    }
    return chemins.sort();
  });
  expect(cache).toEqual(["/faq", "/infos", "/programme"]);

  await eteindre();

  await page.goto(`${BASE}/programme`);
  await expect(page.getByRole("heading", { name: "Le programme" })).toBeVisible();
  await expect(page.getByText("L’Éclat", { exact: false }).first()).toBeVisible();

  await page.goto(`${BASE}/infos`);
  await expect(page.getByText("Domaine de Roiffé, 86120 Roiffé (Vienne)")).toBeVisible();

  await page.goto(`${BASE}/faq`);
  await expect(page.getByText("18 questions")).toBeVisible();
  // La recherche se fait dans le téléphone : elle marche sans réseau.
  await page.getByLabel("Chercher une question").fill("fauteuil");
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(1);
});

test("une page personnelle n'est jamais mise en cache : l'écran hors ligne prend le relais", async ({
  page,
}) => {
  await page.goto(`${BASE}/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await attendreServiceWorker(page);
  await page.goto(`${BASE}/`);
  await page.waitForLoadState("networkidle");
  await page.goto(`${BASE}/programme`);
  await page.waitForLoadState("networkidle");

  // Aucun cache ne doit contenir une page portant le nom du foyer.
  const contenus = await page.evaluate(async () => {
    const noms = await caches.keys();
    const chemins: string[] = [];
    for (const nom of noms) {
      for (const requete of await (await caches.open(nom)).keys()) {
        chemins.push(new URL(requete.url).pathname);
      }
    }
    return chemins;
  });
  expect(contenus.filter((chemin) => ["/", "/reponse", "/partager"].includes(chemin))).toEqual([]);

  await eteindre();

  await page.goto(`${BASE}/`);
  await expect(page.getByText(FOYER.label)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Pas de réseau pour l’instant" })).toBeVisible();
  await expect(page.getByText("Tout ce que vous faites sera envoyé dès son retour.")).toBeVisible();
});

test("une réponse donnée sans réseau part au retour du réseau", async ({ page }) => {
  await page.goto(`${BASE}/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();
  await attendreServiceWorker(page);
  await page.goto(`${BASE}/reponse`);
  await page.waitForLoadState("networkidle");

  await eteindre();
  await page.getByRole("button", { name: "Oui", exact: true }).click();

  // L'écran l'annonce sobrement, et rien n'est perdu.
  const indicateur = page.locator("[data-file-attente-indicateur]");
  await expect(indicateur).toContainText("en attente de réseau");
  expect(await enBase("select 1 from public.rsvp")).toHaveLength(0);

  await allumer();
  // Aucune action de l'invité : la file repart d'elle-même.
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect
    .poll(async () => (await enBase("select 1 from public.rsvp")).length, { timeout: 20_000 })
    .toBe(1);
  const lignes = await enBase<{ status: string }>("select status from public.rsvp");
  expect(lignes[0]?.status).toBe("yes");
});
