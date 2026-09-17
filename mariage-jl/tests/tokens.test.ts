import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { MOMENTS, NEUTRES, contraste, luminance } from "@/lib/tokens";

describe("contraste", () => {
  it("encadre correctement les extrêmes", () => {
    expect(luminance("#FFFFFF")).toBeCloseTo(1, 5);
    expect(luminance("#000000")).toBeCloseTo(0, 5);
    expect(contraste("#FFFFFF", "#000000")).toBeCloseTo(21, 2);
  });

  it("refuse un hex invalide plutôt que de deviner", () => {
    expect(() => luminance("bleu")).toThrow();
  });
});

describe("lisibilité des neutres (WCAG 2.2 AA, cible AAA sur le corps de texte)", () => {
  it("ivoire sur noir dépasse 7:1", () => {
    expect(contraste(NEUTRES.ivoire, NEUTRES.noir)).toBeGreaterThanOrEqual(7);
  });

  it("mode Papier dépasse 7:1", () => {
    expect(contraste(NEUTRES.papierTexte, NEUTRES.papierFond)).toBeGreaterThanOrEqual(7);
  });

  it("La Matière reste au-dessus de 3:1 : usage décoratif et gros texte seulement", () => {
    expect(contraste(NEUTRES.matiere, NEUTRES.noir)).toBeGreaterThanOrEqual(3);
  });
});

/**
 * Règle §3 et §17 : les cinq couleurs ne sont jamais une couleur de texte.
 * Ce test vérifie la règle dans le code, pas seulement l'intention.
 */
describe("les cinq couleurs ne portent jamais de texte", () => {
  const racine = join(import.meta.dirname, "..");
  const fichiers = [
    join(racine, "app", "globals.css"),
    ...readdirSync(join(racine, "components"))
      .filter((f) => f.endsWith(".tsx"))
      .map((f) => join(racine, "components", f)),
    ...readdirSync(join(racine, "app"), { recursive: true, encoding: "utf8" })
      .filter((f) => f.endsWith(".tsx"))
      .map((f) => join(racine, "app", f)),
  ];

  const hex = MOMENTS.map((m) => m.hex.toLowerCase());
  const classesInterdites = MOMENTS.map((m) => `text-jl-${m.key}`);

  it.each(fichiers)("%s n'applique aucune couleur de moment à du texte", (fichier) => {
    const contenu = readFileSync(fichier, "utf8").toLowerCase();
    for (const classe of classesInterdites) {
      expect(contenu).not.toContain(classe);
    }
    for (const couleur of hex) {
      // `color: #E9B131` est interdit ; `background: #E9B131` est la règle.
      const motif = new RegExp(`(^|[^-a-z])color\\s*[:=]\\s*["']?${couleur}`, "m");
      expect(contenu).not.toMatch(motif);
    }
  });
});
