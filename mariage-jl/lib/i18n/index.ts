import fr from "./fr.json";
import en from "./en.json";

export const LANGUES = ["fr", "en"] as const;
export type Langue = (typeof LANGUES)[number];
export const LANGUE_DEFAUT: Langue = "fr";
export const COOKIE_LANGUE = "jl_langue";

/** Le dictionnaire français est le contrat : `en` doit en avoir exactement les clés. */
export type Dictionnaire = typeof fr;

const DICTIONNAIRES: Record<Langue, Dictionnaire> = { fr, en };

export function estLangue(valeur: string | undefined): valeur is Langue {
  return valeur === "fr" || valeur === "en";
}

export function dictionnaire(langue: Langue): Dictionnaire {
  return DICTIONNAIRES[langue];
}

/** Remplace les {jetons} d'un libellé. Un jeton inconnu reste visible tel quel. */
export function formater(modele: string, valeurs: Readonly<Record<string, string>>): string {
  return modele.replace(/\{(\w+)\}/g, (entier, cle: string) => valeurs[cle] ?? entier);
}

/** Date lisible dans la langue de l'invité, toujours au fuseau du mariage. */
export function formaterDate(date: Date, langue: Langue): string {
  return new Intl.DateTimeFormat(langue === "fr" ? "fr-FR" : "en-GB", {
    timeZone: "Europe/Paris",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}
