import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
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

  /**
   * Les textes amorcés en base (noms des moments, questions de la FAQ) sont
   * affichés tels quels : ils suivent donc les mêmes règles que les
   * dictionnaires. Un `''` dans une migration produisait une apostrophe droite.
   */
  it("n'amorce aucune apostrophe droite en base", () => {
    const dossier = join(RACINE, "supabase", "migrations");
    for (const fichier of readdirSync(dossier).filter((f) => f.endsWith(".sql"))) {
      const sql = readFileSync(join(dossier, fichier), "utf8");
      const litteraux = sql.match(/'(?:[^']|'')*'/g) ?? [];
      for (const litteral of litteraux) {
        // `''` seul est une chaîne vide ; c'est un `''` À L'INTÉRIEUR d'un
        // texte qui trahit une apostrophe droite.
        const contenu = litteral.slice(1, -1);
        expect(contenu, `${fichier} : ${litteral.slice(0, 60)}`).not.toContain("''");
        // Même règle d'espace insécable que dans les dictionnaires.
        expect(contenu, `${fichier} : ${litteral.slice(0, 60)}`).not.toMatch(/\w [?!;]/);
      }
    }
  });
});
