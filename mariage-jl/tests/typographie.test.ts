import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const RACINE = join(import.meta.dirname, "..");
const NBSP = " ";

/**
 * Règles typographiques du brief §3 : apostrophes typographiques, espaces
 * insécables avant : ; ? !. Vérifiées automatiquement pour qu'une correction
 * manuelle ne se perde pas à la prochaine traduction.
 */
describe("typographie française", () => {
  const dictionnaire = readFileSync(join(RACINE, "lib", "i18n", "fr.json"), "utf8");

  it("n'utilise aucune apostrophe droite", () => {
    expect(dictionnaire).not.toContain("'");
  });

  it("place une espace insécable avant les deux-points, points-virgules et signes doubles", () => {
    expect(dictionnaire).not.toMatch(/ [:;?!]/);
  });

  it("applique les mêmes règles à la page de secours", () => {
    const html = readFileSync(join(RACINE, "secours", "template.html"), "utf8");
    const corps = html.slice(html.indexOf("</style>"));
    expect(corps).not.toContain("'");
    // Les deux-points de `style="background:#..."` ne comptent pas : on ne
    // regarde que ceux précédés d'une espace simple dans du texte.
    expect(corps.replace(/<[^>]+>/g, " ")).not.toMatch(/ [:;?!]/);
  });

  it("garde l'espace insécable disponible comme constante", () => {
    expect(NBSP.charCodeAt(0)).toBe(160);
  });
});
