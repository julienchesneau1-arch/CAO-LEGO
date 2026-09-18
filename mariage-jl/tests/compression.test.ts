import { describe, expect, it } from "vitest";
import { COTE_MAX, DUREE_VIDEO_MAX_S, dimensions } from "@/lib/compression";

/**
 * Redimensionnement avant envoi (brief §8.7). Fonction pure : le reste du
 * module a besoin d'un navigateur, et c'est le parcours Playwright qui le
 * vérifie sur un vrai fichier.
 */
describe("dimensions cibles", () => {
  it("ne grandit jamais une image déjà petite", () => {
    expect(dimensions(800, 600)).toEqual({ largeur: 800, hauteur: 600 });
    expect(dimensions(COTE_MAX, 1000)).toEqual({ largeur: COTE_MAX, hauteur: 1000 });
  });

  it("ramène le plus grand côté à la limite, en gardant les proportions", () => {
    expect(dimensions(4000, 3000)).toEqual({ largeur: 2000, hauteur: 1500 });
    expect(dimensions(3000, 4000)).toEqual({ largeur: 1500, hauteur: 2000 });
  });

  it("ne produit jamais une dimension nulle", () => {
    const petite = dimensions(4000, 1, 100);
    expect(petite.largeur).toBe(100);
    expect(petite.hauteur).toBe(1);
  });

  it("garde la limite de durée du brief", () => {
    expect(DUREE_VIDEO_MAX_S).toBe(60);
  });
});
