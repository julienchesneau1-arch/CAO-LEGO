import { describe, expect, it } from "vitest";
import {
  BLOCS_AVEC_LIEN,
  CLES_BLOCS,
  estCleBloc,
  heureAcceptable,
  jourDeFin,
  lienAcceptable,
  texteOuNull,
} from "@/lib/contenus-admin";

/**
 * Règles de saisie de l'espace « Contenus ». Ce sont des fonctions pures :
 * elles sont vérifiées sans base, donc toujours, même sur une machine sans
 * PostgreSQL.
 */
describe("liens saisis par les mariés", () => {
  it("accepte http et https", () => {
    expect(lienAcceptable("https://exemple.test/liste")).toBe(true);
    expect(lienAcceptable("http://exemple.test")).toBe(true);
  });

  /**
   * Un lien finit dans un `href` vu par tous les invités : un `javascript:`
   * collé par erreur y serait exécutable. Le refus est donc au niveau du
   * schéma, pas d'un filtre d'affichage.
   */
  it("refuse tout ce qui n'est pas http ou https", () => {
    for (const mauvais of [
      "javascript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "file:///etc/passwd",
      "exemple.test",
      "",
      "   ",
    ]) {
      expect(lienAcceptable(mauvais), mauvais).toBe(false);
    }
  });
});

describe("horaires", () => {
  it("n'accepte que HH:MM sur 24 heures", () => {
    for (const bonne of ["00:00", "09:30", "15:05", "23:59"]) {
      expect(heureAcceptable(bonne), bonne).toBe(true);
    }
    for (const mauvaise of ["24:00", "9:30", "15:60", "15h30", "", "15:5"]) {
      expect(heureAcceptable(mauvaise), mauvaise).toBe(false);
    }
  });

  it("place au lendemain une fin antérieure au début", () => {
    expect(jourDeFin("22:00", "03:00")).toBe(1);
    expect(jourDeFin("15:00", "18:00")).toBe(0);
    expect(jourDeFin("15:00", "15:00")).toBe(0);
    expect(jourDeFin(null, "03:00")).toBe(0);
    expect(jourDeFin("22:00", null)).toBe(0);
  });
});

describe("champs de texte", () => {
  it("ramène un champ vidé à null plutôt qu'à une chaîne vide", () => {
    expect(texteOuNull("")).toBeNull();
    expect(texteOuNull("   ")).toBeNull();
    expect(texteOuNull(undefined)).toBeNull();
    expect(texteOuNull("  Roiffé  ")).toBe("Roiffé");
  });
});

describe("clés de blocs", () => {
  it("est un ensemble fermé", () => {
    expect(estCleBloc("infos.venir")).toBe(true);
    expect(estCleBloc("infos.inconnu")).toBe(false);
    expect(estCleBloc(undefined)).toBe(false);
  });

  it("ne porte un lien que là où l'écran invité en affiche un", () => {
    for (const cle of BLOCS_AVEC_LIEN) {
      expect(CLES_BLOCS as readonly string[]).toContain(cle);
    }
    expect(BLOCS_AVEC_LIEN.has("infos.venir")).toBe(false);
    expect(BLOCS_AVEC_LIEN.has("loin.diffusion")).toBe(true);
  });
});
