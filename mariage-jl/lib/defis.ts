import "server-only";
import { requete } from "./db";
import type { Langue } from "./i18n";

/**
 * Défis photo (brief §8.7, bonus de la section 0 bis) : un par moment, dans
 * sa couleur.
 *
 * Deux règles, et elles viennent du §17 :
 * — **aucun classement, aucun compteur.** On ne dit jamais combien de
 *   personnes ont répondu à un défi, ni qui. Un défi est une invitation à
 *   regarder autrement, pas une compétition.
 * — **rien n'est inventé.** Un défi sans intitulé écrit n'apparaît pas :
 *   le brief dit « intitulés éditables » et ne les fournit pas.
 */
export type Defi = {
  readonly id: string;
  readonly moment_id: string;
  readonly titre: string;
  readonly published: boolean;
};

const EN_ATTENTE = (titre: string): boolean =>
  titre.trim() === "" ||
  titre.includes("[À COMPLÉTER]") ||
  titre.includes("[TO BE COMPLETED]");

/** Les défis visibles des invités : publiés et réellement écrits. */
export async function defisPublies(langue: Langue): Promise<ReadonlyArray<Defi>> {
  const colonne = langue === "fr" ? "title_fr" : "title_en";
  const lignes = await requete<Defi>(
    `select id, moment_id, ${colonne} as titre, published
       from public.photo_challenges
      where published order by moment_id`,
  );
  return lignes.filter((defi) => !EN_ATTENTE(defi.titre));
}

/** Tous les défis, pour l'écran des mariés : intitulés vides compris. */
export async function defisAdmin(): Promise<
  ReadonlyArray<{
    readonly id: string;
    readonly moment_id: string;
    readonly title_fr: string;
    readonly title_en: string;
    readonly published: boolean;
  }>
> {
  return requete(
    `select id, moment_id, title_fr, title_en, published
       from public.photo_challenges order by moment_id`,
  );
}

export async function enregistrerDefi(
  id: string,
  valeurs: {
    readonly title_fr: string;
    readonly title_en: string;
    readonly published: boolean;
  },
): Promise<void> {
  await requete(
    `update public.photo_challenges
        set title_fr = $2, title_en = $3, published = $4
      where id = $1`,
    [id, valeurs.title_fr, valeurs.title_en, valeurs.published],
  );
}

export async function estDefiOuvert(id: string): Promise<boolean> {
  const lignes = await requete<{ n: number }>(
    `select count(*)::int as n from public.photo_challenges
      where id = $1 and published and title_fr not like '%[À COMPLÉTER]%'`,
    [id],
  );
  return Number(lignes[0]?.n ?? 0) > 0;
}
