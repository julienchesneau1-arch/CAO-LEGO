import "server-only";
import { requete } from "./db";
import type { Langue } from "./i18n";

export type Moment = {
  readonly id: string;
  readonly name_fr: string;
  readonly name_en: string;
  readonly kind_fr: string;
  readonly kind_en: string;
  readonly color_token: string;
  readonly starts_at: Date | null;
  readonly ends_at: Date | null;
  readonly place: string | null;
  readonly ambience_fr: string | null;
  readonly ambience_en: string | null;
  readonly detail_fr: string | null;
  readonly detail_en: string | null;
  readonly shift_minutes: number;
};

/**
 * Les cinq moments, décalage de la régie déjà appliqué aux horaires (§9).
 * Les horaires sont nuls tant qu'ils ne sont pas connus : l'écran affiche
 * alors « [À COMPLÉTER] » et n'invente rien.
 */
export async function moments(): Promise<ReadonlyArray<Moment>> {
  return requete<Moment>(
    `select id, name_fr, name_en, kind_fr, kind_en, color_token,
            starts_at + (shift_minutes || ' minutes')::interval as starts_at,
            ends_at   + (shift_minutes || ' minutes')::interval as ends_at,
            place, ambience_fr, ambience_en, detail_fr, detail_en, shift_minutes
       from public.moments
      order by id`,
  );
}

export const nomMoment = (moment: Moment, langue: Langue): string =>
  langue === "fr" ? moment.name_fr : moment.name_en;

export const genreMoment = (moment: Moment, langue: Langue): string =>
  langue === "fr" ? moment.kind_fr : moment.kind_en;

export const ambianceMoment = (moment: Moment, langue: Langue): string | null =>
  langue === "fr" ? moment.ambience_fr : moment.ambience_en;

export const detailMoment = (moment: Moment, langue: Langue): string | null =>
  langue === "fr" ? moment.detail_fr : moment.detail_en;

/** Heure lisible au fuseau du mariage, ou rien si l'horaire est inconnu. */
export function heure(date: Date | null, langue: Langue): string | null {
  if (date === null) return null;
  return new Intl.DateTimeFormat(langue === "fr" ? "fr-FR" : "en-GB", {
    timeZone: "Europe/Paris",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
