import "server-only";
import { une } from "./db";
import { type Moment, moments } from "./moments";

/**
 * État de la journée (brief §8.6). Tout est calculé à partir des horaires
 * saisis par les mariés, décalage de la régie compris : aucune heure n'est
 * codée en dur, et tant qu'aucun horaire n'est écrit l'écran le dit au lieu
 * d'inventer un « en cours ».
 */
export type EtatJournee = {
  /** Moment commencé et pas encore fini. */
  readonly courant: Moment | undefined;
  /** Premier moment qui n'a pas encore commencé. */
  readonly suivant: Moment | undefined;
  readonly horairesConnus: boolean;
  /** Réglage : la cérémonie coupe-t-elle les envois ? */
  readonly ceremonieDebranchee: boolean;
  /** Coupure posée à la main par la régie. */
  readonly pauseManuelle: boolean;
  /** Les envois sont-ils coupés, maintenant ? */
  readonly envoisEnPause: boolean;
  /** Sommes-nous pendant la cérémonie débranchée ? */
  readonly pendantCeremonie: boolean;
};

/** Le moment de la cérémonie, celui qui se vit sans téléphone (brief §8.6). */
export const MOMENT_CEREMONIE = "02";

/**
 * Découpe la liste des moments autour d'un instant. Fonction pure, séparée
 * de la base : c'est elle qui porte la règle, donc c'est elle qu'on teste.
 */
export function situer(
  liste: ReadonlyArray<Moment>,
  instant: Date,
): { readonly courant: Moment | undefined; readonly suivant: Moment | undefined } {
  const t = instant.getTime();
  let courant: Moment | undefined;
  let suivant: Moment | undefined;

  for (const moment of liste) {
    if (moment.starts_at === null) continue;
    const debut = moment.starts_at.getTime();
    if (debut <= t) {
      // Un moment sans fin déclarée court jusqu'au début du suivant : c'est
      // le cas de « La Nuit », qui ne se termine pas à une heure connue.
      const fin = moment.ends_at?.getTime();
      if (fin === undefined || fin > t) courant = moment;
    } else if (suivant === undefined) {
      suivant = moment;
    }
  }
  return { courant, suivant };
}

export async function etatJournee(instant = new Date()): Promise<EtatJournee> {
  const [liste, reglages] = await Promise.all([
    moments(),
    une<{ ceremonie_debranchee: boolean; photos_en_pause: boolean }>(
      "select ceremonie_debranchee, photos_en_pause from public.parametres where id = 1",
    ),
  ]);

  const { courant, suivant } = situer(liste, instant);
  const ceremonieDebranchee = reglages?.ceremonie_debranchee ?? true;
  const pauseManuelle = reglages?.photos_en_pause ?? false;
  const pendantCeremonie = ceremonieDebranchee && courant?.id === MOMENT_CEREMONIE;

  return {
    courant,
    suivant,
    horairesConnus: liste.some((moment) => moment.starts_at !== null),
    ceremonieDebranchee,
    pauseManuelle,
    // La pause de la cérémonie se lève d'elle-même à la fin de L'Horizon ;
    // celle de la régie demande un geste. Les deux coupent les envois.
    envoisEnPause: pauseManuelle || pendantCeremonie,
    pendantCeremonie,
  };
}

/** Minutes restantes avant le début d'un moment, arrondies à la minute basse. */
export function minutesAvant(moment: Moment | undefined, instant: Date): number | undefined {
  if (moment?.starts_at === undefined || moment.starts_at === null) return undefined;
  const ecart = moment.starts_at.getTime() - instant.getTime();
  return ecart <= 0 ? 0 : Math.floor(ecart / 60_000);
}
