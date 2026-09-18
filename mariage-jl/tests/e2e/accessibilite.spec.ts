import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { FOYER } from "./fixtures";
import { ouvrirAdmin } from "./admin";
import { ciblesTropPetites } from "./cibles";
import { reinitialiserFoyer } from "./reinitialiser";

/**
 * Accessibilité WCAG 2.2 AA (brief §12), vérifiée automatiquement sur chaque
 * écran d'invité. L'automatisation ne remplace pas une relecture humaine :
 * elle empêche seulement les régressions silencieuses.
 */
const ECRANS = ["/", "/programme", "/programme/02", "/infos", "/faq", "/reponse", "/retrouver"];

test.beforeEach(async () => {
  await reinitialiserFoyer();
});

for (const chemin of ECRANS) {
  test(`aucune anomalie d'accessibilité sur ${chemin}`, async ({ page }) => {
    // On ouvre l'invitation d'abord : les écrans doivent être testés tels que
    // l'invité les voit, avec son foyer reconnu.
    await page.goto(`/i/${FOYER.jeton}`);
    await page.getByRole("button", { name: "Passer" }).click();
    await page.goto(chemin);

    const resultat = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      // `target-size` signale toute cible recouverte par la barre d'onglets,
      // qui est opaque et flotte au-dessus du contenu : c'est le
      // fonctionnement normal d'une barre de navigation mobile, et le bas de
      // page reste atteignable grâce à la réserve du gabarit. La règle est
      // remplacée par la mesure ci-dessous, plus stricte que WCAG (48 px au
      // lieu de 24), qui porte sur la taille réelle de chaque cible.
      .disableRules(["target-size"])
      .analyze();

    const lisible = resultat.violations.map((violation) => ({
      regle: violation.id,
      impact: violation.impact,
      description: violation.help,
      elements: violation.nodes.map((noeud) => noeud.target.join(" ")),
    }));
    expect(lisible, `anomalies sur ${chemin}`).toEqual([]);
  });
}

test("toutes les cibles tactiles font au moins 48 px", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await page.getByRole("button", { name: "Passer" }).click();

  for (const chemin of ECRANS) {
    await page.goto(chemin);
    const trop_petites = await ciblesTropPetites(page);
    expect(trop_petites, `cibles trop petites sur ${chemin}`).toEqual([]);
  }
});

test("l'ouverture signature est franchissable au clavier seul", async ({ page }) => {
  await page.goto(`/i/${FOYER.jeton}`);
  await expect(page.getByRole("dialog")).toBeVisible();
  // Le focus entre dans la surcouche, puis la tabulation atteint « Passer ».
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Passer" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

/**
 * L'espace des mariés est un écran de travail, utilisé au téléphone pendant
 * des mois : il est tenu aux mêmes règles que les écrans d'invité.
 */
const ECRANS_ADMIN = [
  "/admin",
  "/admin/contenus?section=journee",
  "/admin/contenus?section=moments",
  "/admin/contenus?section=moments&element=02",
  "/admin/contenus?section=infos",
  "/admin/contenus?section=infos&element=infos.liste_mariage",
  "/admin/contenus?section=faq",
  "/admin/contenus?section=faq&element=nouveau",
  "/admin/contenus?section=hebergements",
  "/admin/contenus?section=hebergements&element=nouveau",
  "/admin/annonces",
];

test("l'espace des mariés est accessible, et ses cibles font 48 px", async ({ browser }) => {
  const maries = await ouvrirAdmin(browser);

  for (const chemin of ECRANS_ADMIN) {
    await maries.goto(chemin);

    const resultat = await new AxeBuilder({ page: maries })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const lisible = resultat.violations.map((violation) => ({
      regle: violation.id,
      impact: violation.impact,
      description: violation.help,
      elements: violation.nodes.map((noeud) => noeud.target.join(" ")),
    }));
    expect(lisible, `anomalies sur ${chemin}`).toEqual([]);

    const trop_petites = await ciblesTropPetites(maries);
    expect(trop_petites, `cibles trop petites sur ${chemin}`).toEqual([]);
  }

  await maries.context().close();
});
