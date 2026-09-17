import { describe, expect, it } from "vitest";
import { restant } from "@/lib/compte";
import { etapesFranchies, joursAvant, periodeEffective, periodePour } from "@/lib/periode";

const MARIAGE = new Date("2028-06-03T00:00:00+02:00");
const paris = (iso: string): Date => new Date(iso);

describe("bascule des périodes", () => {
  it("place la veille du mariage en semaine J", () => {
    expect(periodePour(paris("2028-06-02T23:59:00+02:00"), MARIAGE)).toBe("semaine");
  });

  it("place le jour du mariage en jour J, dès minuit à Paris", () => {
    expect(periodePour(paris("2028-06-03T00:01:00+02:00"), MARIAGE)).toBe("jour");
    expect(periodePour(paris("2028-06-03T23:59:00+02:00"), MARIAGE)).toBe("jour");
  });

  it("passe en après dès le lendemain", () => {
    expect(periodePour(paris("2028-06-04T00:05:00+02:00"), MARIAGE)).toBe("apres");
  });

  it("garde « avant » jusqu'à J-8 inclus", () => {
    expect(periodePour(paris("2028-05-26T12:00:00+02:00"), MARIAGE)).toBe("avant");
    expect(periodePour(paris("2028-05-27T12:00:00+02:00"), MARIAGE)).toBe("semaine");
  });

  it("raisonne en jour civil parisien, pas en fuseau du téléphone", () => {
    // 23 h 30 à Montréal le 2 juin = 5 h 30 à Paris le 3 juin : c'est le jour J.
    expect(periodePour(new Date("2028-06-02T23:30:00-04:00"), MARIAGE)).toBe("jour");
  });

  it("compte les jours restants sans se tromper d'un cran", () => {
    expect(joursAvant(paris("2028-06-03T10:00:00+02:00"), MARIAGE)).toBe(0);
    expect(joursAvant(paris("2028-06-02T10:00:00+02:00"), MARIAGE)).toBe(1);
    expect(joursAvant(paris("2026-09-17T10:00:00+02:00"), MARIAGE)).toBe(625);
  });
});

describe("bascule manuelle de l'admin", () => {
  const maintenant = paris("2026-09-17T10:00:00+02:00");

  it("prime sur le calendrier", () => {
    expect(periodeEffective(maintenant, MARIAGE, { periode: "jour", jusqua: null })).toBe("jour");
  });

  it("expire toute seule", () => {
    const expiree = { periode: "jour" as const, jusqua: paris("2026-09-17T09:00:00+02:00") };
    expect(periodeEffective(maintenant, MARIAGE, expiree)).toBe("avant");
  });

  it("ignore une bascule vide", () => {
    expect(periodeEffective(maintenant, MARIAGE, { periode: null, jusqua: null })).toBe("avant");
  });
});

describe("fil des cinq étapes", () => {
  it("n'allume « réponse » que si le foyer a répondu", () => {
    const sans = etapesFranchies(paris("2026-09-17T10:00:00+02:00"), MARIAGE, false);
    expect(sans.find((e) => e.etape === "reponse")?.franchie).toBe(false);
    const avec = etapesFranchies(paris("2026-09-17T10:00:00+02:00"), MARIAGE, true);
    expect(avec.find((e) => e.etape === "reponse")?.franchie).toBe(true);
  });

  it("allume tout le jour J", () => {
    const etapes = etapesFranchies(paris("2028-06-03T09:00:00+02:00"), MARIAGE, true);
    expect(etapes.every((e) => e.franchie)).toBe(true);
  });
});

describe("décompte", () => {
  it("découpe le temps restant sans perdre une seconde", () => {
    const cible = Date.UTC(2028, 5, 3, 0, 0, 0);
    const maintenant = cible - ((2 * 86_400 + 3 * 3_600 + 4 * 60 + 5) * 1000);
    expect(restant(cible, maintenant)).toEqual({ jours: 2, heures: 3, minutes: 4, secondes: 5 });
  });

  it("s'arrête à zéro et ne compte jamais à l'envers", () => {
    expect(restant(1_000, 9_999_999)).toEqual({ jours: 0, heures: 0, minutes: 0, secondes: 0 });
  });
});
