import { describe, expect, it } from "vitest";
import { lireCsvFoyers } from "@/lib/csv";

describe("import CSV des invités", () => {
  it("lit un fichier simple, en-tête comprise", () => {
    const { foyers, erreurs } = lireCsvFoyers(
      "foyer;invites;langue\nFamille Exemple;Prénom A|Prénom B;fr\nFoyer Seul;Prénom C;en\n",
    );
    expect(erreurs).toEqual([]);
    expect(foyers).toEqual([
      { foyer: "Famille Exemple", invites: ["Prénom A", "Prénom B"], langue: "fr" },
      { foyer: "Foyer Seul", invites: ["Prénom C"], langue: "en" },
    ]);
  });

  it("supporte la marque d'octets d'Excel et les retours Windows", () => {
    const { foyers } = lireCsvFoyers("﻿foyer;invites\r\nFamille;Prénom\r\n");
    expect(foyers).toHaveLength(1);
    expect(foyers[0]?.langue).toBe("fr");
  });

  it("respecte les guillemets autour d'un champ contenant un point-virgule", () => {
    const { foyers } = lireCsvFoyers('"Famille Dupont; et Cie";Prénom\n');
    expect(foyers[0]?.foyer).toBe("Famille Dupont; et Cie");
  });

  it("signale les lignes inutilisables sans faire échouer le reste", () => {
    const { foyers, erreurs } = lireCsvFoyers(";Prénom\nFamille;\nBonne;Prénom\n");
    expect(foyers.map((f) => f.foyer)).toEqual(["Bonne"]);
    expect(erreurs).toHaveLength(2);
    expect(erreurs[0]).toContain("Ligne 1");
    expect(erreurs[1]).toContain("Ligne 2");
  });

  it("refuse une langue inconnue plutôt que de la deviner", () => {
    const { foyers, erreurs } = lireCsvFoyers("Famille;Prénom;de\n");
    expect(foyers).toEqual([]);
    expect(erreurs[0]).toContain("langue");
  });
});
