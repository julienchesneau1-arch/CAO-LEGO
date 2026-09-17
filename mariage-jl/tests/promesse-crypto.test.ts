import { describe, expect, it } from "vitest";
import {
  desceller,
  importerClePrivee,
  importerClePublique,
  sceller,
  type Enveloppe,
} from "@/lib/promesse-crypto";

/**
 * La promesse : ce que ces tests garantissent, c'est qu'un vœu scellé est
 * illisible sans la clé privée — la seule chose qui rend honnête la phrase
 * « invisibles de tous, y compris des mariés ».
 */
async function paire(): Promise<{ publique: string; privee: string }> {
  const { publicKey, privateKey } = await crypto.subtle.generateKey(
    { name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["encrypt", "decrypt"],
  );
  const base64 = (o: ArrayBuffer): string => Buffer.from(o).toString("base64");
  return {
    publique: base64(await crypto.subtle.exportKey("spki", publicKey)),
    privee: base64(await crypto.subtle.exportKey("pkcs8", privateKey)),
  };
}

const VOEU =
  "Que vos disputes soient courtes et vos réconciliations longues. Et qu’il y ait toujours du vin.";

describe("scellement d'un vœu", () => {
  it("se rouvre avec la bonne clé privée, mot pour mot", async () => {
    const cles = await paire();
    const enveloppe = await sceller(VOEU, await importerClePublique(cles.publique));
    const ouvert = await desceller(enveloppe, await importerClePrivee(cles.privee));
    expect(ouvert).toBe(VOEU);
  });

  it("ne laisse fuir aucun mot du vœu dans l'enveloppe", async () => {
    const cles = await paire();
    const enveloppe = await sceller(VOEU, await importerClePublique(cles.publique));
    const stocke = JSON.stringify(enveloppe);
    for (const mot of ["disputes", "réconciliations", "vin"]) {
      expect(stocke).not.toContain(mot);
    }
    expect(stocke).not.toContain(VOEU);
  });

  it("résiste à une autre clé privée", async () => {
    const bonnes = await paire();
    const autres = await paire();
    const enveloppe = await sceller(VOEU, await importerClePublique(bonnes.publique));
    await expect(desceller(enveloppe, await importerClePrivee(autres.privee))).rejects.toThrow();
  });

  it("refuse une enveloppe modifiée, même d'un octet", async () => {
    const cles = await paire();
    const enveloppe = await sceller(VOEU, await importerClePublique(cles.publique));
    const octets = Buffer.from(enveloppe.texte, "base64");
    octets[0] = (octets[0] ?? 0) ^ 0x01;
    const falsifiee: Enveloppe = { ...enveloppe, texte: octets.toString("base64") };
    await expect(desceller(falsifiee, await importerClePrivee(cles.privee))).rejects.toThrow();
  });

  it("tire un vecteur d'initialisation différent à chaque vœu", async () => {
    const cles = await paire();
    const publique = await importerClePublique(cles.publique);
    const premiere = await sceller(VOEU, publique);
    const seconde = await sceller(VOEU, publique);
    expect(premiere.iv).not.toBe(seconde.iv);
    expect(premiere.texte).not.toBe(seconde.texte);
  });

  it("refuse une enveloppe de version inconnue plutôt que de deviner", async () => {
    const cles = await paire();
    const enveloppe = await sceller(VOEU, await importerClePublique(cles.publique));
    const future = { ...enveloppe, v: 2 } as unknown as Enveloppe;
    await expect(desceller(future, await importerClePrivee(cles.privee))).rejects.toThrow(
      /version inconnue/,
    );
  });
});
