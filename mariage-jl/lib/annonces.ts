import "server-only";
import { requete, une } from "./db";
import type { Langue } from "./i18n";

export type Annonce = {
  readonly id: string;
  readonly texte: string;
  readonly published_at: Date;
  readonly author_role: string;
};

/**
 * Fil d'annonces (brief §8.6 et V2). Les annonces sont publiques à tous les
 * invités : aucune donnée personnelle n'y entre, ce qui permet aussi de les
 * afficher depuis le QR générique.
 */
export async function annonces(langue: Langue, limite = 20): Promise<ReadonlyArray<Annonce>> {
  const colonne = langue === "fr" ? "body_fr" : "body_en";
  return requete<Annonce>(
    `select id, ${colonne} as texte, published_at, author_role
       from public.announcements
      order by published_at desc
      limit $1`,
    [limite],
  );
}

export async function derniereAnnonce(langue: Langue): Promise<Annonce | undefined> {
  return (await annonces(langue, 1))[0];
}

/** Publication par les mariés. La régie aura son propre écran en V3. */
export async function publierAnnonce(
  texteFr: string,
  texteEn: string,
  role: "admin" | "regie",
): Promise<string | undefined> {
  const ligne = await une<{ id: string }>(
    `insert into public.announcements (body_fr, body_en, author_role)
     values ($1, $2, $3) returning id`,
    [texteFr, texteEn, role],
  );
  return ligne?.id;
}
