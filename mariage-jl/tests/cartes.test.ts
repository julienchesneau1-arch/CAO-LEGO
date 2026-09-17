import { describe, expect, it } from "vitest";
import { itineraires } from "@/lib/cartes";

describe("boutons d'itinéraire", () => {
  const liste = itineraires("Domaine de Roiffé, 86120 Roiffé");

  it("propose Apple Plans, Google Maps et Waze", () => {
    expect(liste.map((i) => i.cle)).toEqual(["apple", "google", "waze"]);
  });

  it("encode la destination, accents et virgules compris", () => {
    for (const itineraire of liste) {
      expect(itineraire.url).toContain("Domaine%20de%20Roiff%C3%A9");
      expect(itineraire.url).not.toContain(" ");
      expect(itineraire.url.startsWith("https://")).toBe(true);
    }
  });

  it("n'invente aucune coordonnée", () => {
    for (const itineraire of liste) {
      expect(itineraire.url).not.toMatch(/\d+\.\d{4,},\s*-?\d+\.\d{4,}/);
    }
  });
});
