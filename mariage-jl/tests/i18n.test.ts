import { describe, expect, it } from "vitest";
import { LANGUES, dictionnaire } from "@/lib/i18n";

const aplatir = (objet: unknown, prefixe = ""): string[] =>
  Object.entries(objet as Record<string, unknown>).flatMap(([cle, valeur]) => {
    const chemin = prefixe ? `${prefixe}.${cle}` : cle;
    return typeof valeur === "object" && valeur !== null ? aplatir(valeur, chemin) : [chemin];
  });

describe("traductions", () => {
  it("expose exactement les mêmes clés en français et en anglais", () => {
    const [premier, ...autres] = LANGUES.map((l) => aplatir(dictionnaire(l)).sort());
    for (const autre of autres) expect(autre).toEqual(premier);
  });

  it("ne contient aucune valeur vide", () => {
    for (const langue of LANGUES) {
      const plat = JSON.stringify(dictionnaire(langue));
      expect(plat).not.toMatch(/:\s*""/);
    }
  });
});
