/**
 * Périodes de l'application (brief §7). Calculées en Europe/Paris, jamais
 * depuis le fuseau du téléphone : deux invités dans deux pays voient la même
 * chose. L'admin peut forcer une période, et les tests simulent l'horloge.
 */
export const PERIODES = ["avant", "semaine", "jour", "apres"] as const;
export type Periode = (typeof PERIODES)[number];

export const FUSEAU = "Europe/Paris";

export function estPeriode(valeur: string | undefined): valeur is Periode {
  return valeur !== undefined && (PERIODES as readonly string[]).includes(valeur);
}

/** Jour civil à Paris, ramené à un nombre de jours : comparable sans heure. */
export function jourParis(instant: Date): number {
  const parties = new Intl.DateTimeFormat("fr-FR", {
    timeZone: FUSEAU,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(instant);
  const lire = (type: string): number => Number(parties.find((p) => p.type === type)?.value ?? "0");
  return Math.floor(Date.UTC(lire("year"), lire("month") - 1, lire("day")) / 86_400_000);
}

/** Jours restants avant le mariage : 0 le jour J, négatif après. */
export function joursAvant(maintenant: Date, dateMariage: Date): number {
  return jourParis(dateMariage) - jourParis(maintenant);
}

export function periodePour(maintenant: Date, dateMariage: Date): Periode {
  const jours = joursAvant(maintenant, dateMariage);
  if (jours >= 8) return "avant";
  if (jours >= 1) return "semaine";
  if (jours === 0) return "jour";
  return "apres";
}

/**
 * Période effective : la bascule manuelle de l'admin prime, tant qu'elle n'est
 * pas expirée (brief §7).
 */
export function periodeEffective(
  maintenant: Date,
  dateMariage: Date,
  forcee?: { periode: Periode | null; jusqua: Date | null },
): Periode {
  if (forcee?.periode != null) {
    const valide = forcee.jusqua === null || forcee.jusqua.getTime() > maintenant.getTime();
    if (valide) return forcee.periode;
  }
  return periodePour(maintenant, dateMariage);
}

/** Les cinq étapes du fil d'attente de l'accueil (brief §8.1). */
export const ETAPES = ["annonce", "reponse", "j30", "j7", "jourj"] as const;
export type Etape = (typeof ETAPES)[number];

export function etapesFranchies(
  maintenant: Date,
  dateMariage: Date,
  aRepondu: boolean,
): ReadonlyArray<{ etape: Etape; franchie: boolean }> {
  const jours = joursAvant(maintenant, dateMariage);
  return [
    { etape: "annonce", franchie: true },
    { etape: "reponse", franchie: aRepondu },
    { etape: "j30", franchie: jours <= 30 },
    { etape: "j7", franchie: jours <= 7 },
    { etape: "jourj", franchie: jours <= 0 },
  ];
}
