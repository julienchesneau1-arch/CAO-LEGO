import { describe, expect, it } from "vitest";
import { PDFDocument } from "pdf-lib";
import { planchePdf } from "@/lib/planche-qr";

describe("planche QR", () => {
  const foyers = Array.from({ length: 9 }, (_, index) => ({
    label: `Foyer d'essai ${index + 1}`,
    jeton: `jeton${index}`.padEnd(32, "x"),
    code: "AB12CD",
  }));

  it("produit un PDF valide", async () => {
    const pdf = await planchePdf(foyers.slice(0, 1), { domaine: "exemple.test" });
    expect(Buffer.from(pdf.slice(0, 5)).toString("ascii")).toBe("%PDF-");
    expect(pdf.byteLength).toBeGreaterThan(1_000);
  });

  it("passe à la page suivante au-delà de huit foyers", async () => {
    // On relit le PDF produit plutôt que d'inspecter ses octets : c'est le
    // même lecteur que celui d'un navigateur ou d'une imprimante.
    const compter = async (nombre: number): Promise<number> => {
      const pdf = await planchePdf(foyers.slice(0, nombre), { domaine: "exemple.test" });
      return (await PDFDocument.load(pdf)).getPageCount();
    };
    expect(await compter(8)).toBe(1);
    expect(await compter(9)).toBe(2);
  });

  it("ne produit jamais une planche vide", async () => {
    const pdf = await planchePdf([], { domaine: "exemple.test" });
    expect(Buffer.from(pdf.slice(0, 5)).toString("ascii")).toBe("%PDF-");
  });
});
