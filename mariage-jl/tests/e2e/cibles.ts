import type { Page } from "@playwright/test";

export type Cible = {
  readonly balise: string;
  readonly nom: string;
  readonly hauteur: number;
  readonly largeur: number;
};

/**
 * Cibles tactiles plus petites que 48 px (brief §12), mesurées sur leur
 * encombrement réel.
 *
 * Seule exception : une case à cocher ou un bouton radio enveloppé dans son
 * étiquette. Le carré dessiné par le navigateur fait 24 px, mais la zone
 * cliquable est l'étiquette entière — c'est donc elle qu'on mesure. Un champ
 * de texte, lui, est mesuré sur lui-même : son étiquette n'agrandit pas la
 * zone où l'on peut taper.
 */
export async function ciblesTropPetites(page: Page): Promise<ReadonlyArray<Cible>> {
  return page.evaluate(() => {
    const cibles = [
      ...document.querySelectorAll(
        "a[href], button, input:not([type=hidden]), summary, select, textarea",
      ),
    ];
    return cibles
      .map((element) => {
        const coche =
          element instanceof HTMLInputElement &&
          (element.type === "checkbox" || element.type === "radio");
        const etiquette = coche ? element.closest("label") : null;
        const boite = (etiquette ?? element).getBoundingClientRect();
        return {
          balise: element.tagName.toLowerCase(),
          nom: element.getAttribute("name") ?? (element.textContent ?? "").trim().slice(0, 30),
          hauteur: Math.round(boite.height),
          largeur: Math.round(boite.width),
        };
      })
      .filter((cible) => cible.hauteur > 0 && (cible.hauteur < 48 || cible.largeur < 24));
  });
}
