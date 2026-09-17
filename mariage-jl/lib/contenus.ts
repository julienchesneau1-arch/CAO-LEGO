import "server-only";
import { requete } from "./db";
import type { Langue } from "./i18n";

export type Contenu = { readonly texte: string; readonly lien: string | null };

/** Blocs éditables d'une langue, indexés par clé. */
export async function contenus(langue: Langue): Promise<Readonly<Record<string, Contenu>>> {
  const lignes = await requete<{ key: string; value: { texte?: string; lien?: string | null } }>(
    "select key, value from public.content_blocks where locale = $1",
    [langue],
  );
  const table: Record<string, Contenu> = {};
  for (const ligne of lignes) {
    table[ligne.key] = {
      texte: ligne.value.texte ?? "",
      lien: ligne.value.lien ?? null,
    };
  }
  return table;
}

export type QuestionFaq = {
  readonly id: string;
  readonly question: string;
  readonly reponse: string;
};

export async function faq(langue: Langue): Promise<ReadonlyArray<QuestionFaq>> {
  const colonneQuestion = langue === "fr" ? "question_fr" : "question_en";
  const colonneReponse = langue === "fr" ? "answer_fr" : "answer_en";
  return requete<QuestionFaq>(
    `select id, ${colonneQuestion} as question, ${colonneReponse} as reponse
       from public.faq where published order by sort_order`,
  );
}

export type Hebergement = {
  readonly id: string;
  readonly name: string;
  readonly distance_km: string | null;
  readonly price_hint: string | null;
  readonly url: string | null;
  readonly phone: string | null;
  readonly shuttle: boolean | null;
};

/** Hébergements éditables depuis l'admin (brief §8.4). */
export async function hebergements(): Promise<ReadonlyArray<Hebergement>> {
  return requete<Hebergement>(
    `select id, name, distance_km, price_hint, url, phone, shuttle
       from public.accommodations order by sort_order, name`,
  );
}
