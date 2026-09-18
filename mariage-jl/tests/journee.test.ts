import { describe, expect, it } from "vitest";
import { MOMENT_CEREMONIE, minutesAvant, situer } from "@/lib/journee";
import { famille } from "@/lib/meteo";
import type { Moment } from "@/lib/moments";

/**
 * Situer l'instant dans la journée (brief §8.6). Règle pure, testée seule :
 * c'est elle qui décide de ce qui s'affiche en grand le jour J, et une erreur
 * ici se verrait de tous les invités en même temps.
 */
const JOUR = "2028-06-03";
const h = (heure: string): Date => new Date(`${JOUR}T${heure}:00.000Z`);

const moment = (id: string, debut: string | null, fin: string | null): Moment => ({
  id,
  name_fr: `Moment ${id}`,
  name_en: `Moment ${id}`,
  kind_fr: "Genre",
  kind_en: "Kind",
  color_token: "eclat",
  starts_at: debut === null ? null : h(debut),
  ends_at: fin === null ? null : h(fin),
  place: null,
  ambience_fr: null,
  ambience_en: null,
  detail_fr: null,
  detail_en: null,
  shift_minutes: 0,
});

const JOURNEE: ReadonlyArray<Moment> = [
  moment("01", "12:00", "14:00"),
  moment("02", "14:00", "15:00"),
  moment("03", "15:00", "18:00"),
  moment("04", "18:00", "21:00"),
  // « La Nuit » n'a pas d'heure de fin connue.
  moment("05", "21:00", null),
];

describe("situer un instant dans la journée", () => {
  it("désigne le moment commencé et pas encore fini", () => {
    const { courant, suivant } = situer(JOURNEE, h("15:30"));
    expect(courant?.id).toBe("03");
    expect(suivant?.id).toBe("04");
  });

  it("n'a rien en cours avant le premier moment", () => {
    const { courant, suivant } = situer(JOURNEE, h("10:00"));
    expect(courant).toBeUndefined();
    expect(suivant?.id).toBe("01");
  });

  /**
   * Un moment sans heure de fin court jusqu'au bout : « La Nuit » reste « en
   * cours » à trois heures du matin, ce qui est exactement le sujet.
   */
  it("garde en cours un moment sans heure de fin", () => {
    const { courant, suivant } = situer(JOURNEE, new Date("2028-06-04T02:00:00.000Z"));
    expect(courant?.id).toBe("05");
    expect(suivant).toBeUndefined();
  });

  it("à la seconde du basculement, le nouveau moment prend la main", () => {
    expect(situer(JOURNEE, h("15:00")).courant?.id).toBe("03");
    expect(situer(JOURNEE, h("14:59")).courant?.id).toBe("02");
  });

  it("n'affiche rien en cours dans un trou entre deux moments", () => {
    const troue = [moment("01", "12:00", "13:00"), moment("03", "15:00", "18:00")];
    const { courant, suivant } = situer(troue, h("14:00"));
    expect(courant).toBeUndefined();
    expect(suivant?.id).toBe("03");
  });

  it("ignore les moments sans horaire au lieu de les inventer", () => {
    const partiels = [moment("01", null, null), moment("02", "14:00", "15:00")];
    const { courant, suivant } = situer(partiels, h("13:00"));
    expect(courant).toBeUndefined();
    expect(suivant?.id).toBe("02");
  });

  it("la cérémonie est bien le deuxième moment", () => {
    expect(MOMENT_CEREMONIE).toBe("02");
  });
});

describe("compte à rebours du moment suivant", () => {
  it("compte les minutes entières restantes", () => {
    expect(minutesAvant(moment("04", "18:00", null), h("17:30"))).toBe(30);
    expect(minutesAvant(moment("04", "18:00", null), h("17:59"))).toBe(1);
  });

  it("ne descend jamais sous zéro", () => {
    expect(minutesAvant(moment("04", "18:00", null), h("18:30"))).toBe(0);
  });

  it("ne dit rien d'un moment sans horaire", () => {
    expect(minutesAvant(moment("04", null, null), h("17:30"))).toBeUndefined();
    expect(minutesAvant(undefined, h("17:30"))).toBeUndefined();
  });
});

describe("familles de météo", () => {
  it("range les codes Open-Meteo en quatre familles", () => {
    expect(famille(0)).toBe("soleil");
    expect(famille(1)).toBe("soleil");
    expect(famille(3)).toBe("nuages");
    expect(famille(61)).toBe("pluie");
    expect(famille(95)).toBe("orage");
  });
});
