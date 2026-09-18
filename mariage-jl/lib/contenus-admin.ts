import "server-only";
import { requete, une } from "./db";
import type { Langue } from "./i18n";

/**
 * Édition des contenus par les mariés (brief §14). Tout ce que le brief
 * marque « [À COMPLÉTER] » se remplit d'ici : horaires des moments, textes
 * des Infos, réponses de la FAQ, hébergements, date limite de réponse.
 *
 * Deux règles tiennent l'ensemble :
 * — chaque formulaire n'écrit **qu'un** élément, pour qu'une saisie au
 *   téléphone ne puisse pas écraser le reste ;
 * — un champ vidé revient à `null`, jamais à la chaîne vide : l'écran invité
 *   sait alors afficher son attente au lieu d'un trou.
 */

/** Blocs de texte éditables, dans l'ordre des écrans invité. */
export const CLES_BLOCS = [
  "infos.venir",
  "infos.dormir",
  "infos.tenue",
  "infos.enfants",
  "infos.accessibilite",
  "infos.rentrer",
  "infos.covoiturage",
  "infos.liste_mariage",
  "loin.diffusion",
  "jour.wifi",
  "apres.merci",
  "apres.film",
] as const;

export type CleBloc = (typeof CLES_BLOCS)[number];

/** Seuls ces blocs portent un lien : ailleurs, un lien serait ignoré. */
export const BLOCS_AVEC_LIEN: ReadonlySet<string> = new Set([
  "infos.covoiturage",
  "infos.liste_mariage",
  "loin.diffusion",
  "apres.film",
]);

export function estCleBloc(valeur: string | undefined): valeur is CleBloc {
  return valeur !== undefined && (CLES_BLOCS as readonly string[]).includes(valeur);
}

/**
 * Contacts joignables depuis l'écran Aide (brief §0 bis : boutons d'appel).
 * Ils ne sont pas dans `CLES_BLOCS` parce qu'ils portent un numéro, pas un
 * lien : un numéro se compose, il ne s'ouvre pas dans un navigateur.
 */
export const CLES_CONTACTS = ["aide.regie", "aide.temoin"] as const;
export type CleContact = (typeof CLES_CONTACTS)[number];

export function estCleContact(valeur: string | undefined): valeur is CleContact {
  return valeur !== undefined && (CLES_CONTACTS as readonly string[]).includes(valeur);
}

/**
 * Numéro de téléphone : chiffres, espaces, points, tirets et un `+` en tête.
 * On ne cherche pas à valider un plan de numérotation — seulement à refuser
 * ce qui ne pourrait pas se composer, et surtout tout ce qui n'est pas un
 * numéro (un `tel:` se retrouve dans un `href`).
 */
export function telephoneAcceptable(valeur: string): boolean {
  const propre = valeur.replace(/[\s.\-()]/g, "");
  return /^\+?\d{6,15}$/.test(propre);
}

/** Forme composable : c'est elle qui part dans `href="tel:…"`. */
export const numeroComposable = (valeur: string): string =>
  valeur.replace(/[\s.\-()]/g, "");

/**
 * Un lien saisi par les mariés finit dans un `href` : on n'accepte que http
 * et https. Sans ce filtre, un `javascript:` collé par erreur deviendrait
 * exécutable pour tous les invités.
 */
export function lienAcceptable(valeur: string): boolean {
  try {
    const url = new URL(valeur);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/** Champ texte d'un formulaire : vidé, il vaut `null`. */
export const texteOuNull = (valeur: string | null | undefined): string | null => {
  const propre = (valeur ?? "").trim();
  return propre === "" ? null : propre;
};

// ------------------------------------------------------------------ Moments

export type MomentAdmin = {
  readonly id: string;
  readonly nom: string;
  readonly genre: string;
  readonly debut: string | null;
  readonly fin: string | null;
  readonly place: string | null;
  readonly ambience_fr: string | null;
  readonly ambience_en: string | null;
  readonly detail_fr: string | null;
  readonly detail_en: string | null;
  readonly shift_minutes: number;
};

/**
 * Les moments tels qu'ils sont **saisis** : heures brutes en Europe/Paris,
 * sans le décalage posé par la régie le jour J. Éditer puis enregistrer
 * redonne donc exactement la même valeur.
 */
export async function momentsAdmin(langue: Langue): Promise<ReadonlyArray<MomentAdmin>> {
  const nom = langue === "fr" ? "name_fr" : "name_en";
  const genre = langue === "fr" ? "kind_fr" : "kind_en";
  return requete<MomentAdmin>(
    `select id, ${nom} as nom, ${genre} as genre,
            to_char(starts_at at time zone 'Europe/Paris', 'HH24:MI') as debut,
            to_char(ends_at   at time zone 'Europe/Paris', 'HH24:MI') as fin,
            place, ambience_fr, ambience_en, detail_fr, detail_en, shift_minutes
       from public.moments order by id`,
  );
}

const HEURE = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;

export const heureAcceptable = (valeur: string): boolean => HEURE.test(valeur);

export type SaisieMoment = {
  readonly debut: string | null;
  readonly fin: string | null;
  readonly place: string | null;
  readonly ambience_fr: string | null;
  readonly ambience_en: string | null;
  readonly detail_fr: string | null;
  readonly detail_en: string | null;
};

/**
 * Une fin antérieure au début appartient au lendemain : « La Nuit » finit à
 * 03:00, pas la veille. Le décalage est calculé ici, en clair, plutôt que
 * caché dans une expression SQL.
 */
export const jourDeFin = (debut: string | null, fin: string | null): number =>
  debut !== null && fin !== null && fin < debut ? 1 : 0;

export async function enregistrerMoment(id: string, saisie: SaisieMoment): Promise<void> {
  await requete(
    `update public.moments set
        starts_at = case when $2::text is null then null
                    else ((select date_mariage from public.parametres where id = 1) + $2::time)
                         at time zone 'Europe/Paris' end,
        ends_at   = case when $3::text is null then null
                    else ((select date_mariage from public.parametres where id = 1) + $3::time
                          + ($4 || ' days')::interval)
                         at time zone 'Europe/Paris' end,
        place = $5, ambience_fr = $6, ambience_en = $7, detail_fr = $8, detail_en = $9
      where id = $1`,
    [
      id,
      saisie.debut,
      saisie.fin,
      String(jourDeFin(saisie.debut, saisie.fin)),
      saisie.place,
      saisie.ambience_fr,
      saisie.ambience_en,
      saisie.detail_fr,
      saisie.detail_en,
    ],
  );
  await journaliser("moment.maj", id);
}

// -------------------------------------------------------------------- Blocs

export type BlocAdmin = {
  readonly cle: string;
  readonly texte_fr: string;
  readonly lien_fr: string | null;
  readonly texte_en: string;
  readonly lien_en: string | null;
};

export async function blocsAdmin(): Promise<ReadonlyArray<BlocAdmin>> {
  const lignes = await requete<{
    key: string;
    locale: string;
    value: { texte?: string; lien?: string | null };
  }>("select key, locale, value from public.content_blocks");

  return CLES_BLOCS.map((cle) => {
    const fr = lignes.find((l) => l.key === cle && l.locale === "fr")?.value ?? {};
    const en = lignes.find((l) => l.key === cle && l.locale === "en")?.value ?? {};
    return {
      cle,
      texte_fr: fr.texte ?? "",
      lien_fr: fr.lien ?? null,
      texte_en: en.texte ?? "",
      lien_en: en.lien ?? null,
    };
  });
}

/**
 * Un bloc s'écrit dans les deux langues d'un coup : laisser une langue en
 * arrière produirait une invitation à moitié traduite, ce que le brief §13
 * interdit.
 */
export async function enregistrerBloc(
  cle: CleBloc,
  valeurs: {
    readonly texte_fr: string;
    readonly texte_en: string;
    readonly lien: string | null;
  },
  par: string,
): Promise<void> {
  const lien = BLOCS_AVEC_LIEN.has(cle) ? valeurs.lien : null;
  const charge = (texte: string): string => JSON.stringify({ texte, lien });
  await requete(
    `insert into public.content_blocks (key, locale, value, updated_at, updated_by)
     values ($1, 'fr', $2::jsonb, now(), $4), ($1, 'en', $3::jsonb, now(), $4)
     on conflict (key, locale) do update
        set value = excluded.value, updated_at = now(), updated_by = excluded.updated_by`,
    [cle, charge(valeurs.texte_fr), charge(valeurs.texte_en), par],
  );
  await journaliser("bloc.maj", cle);
}

export type ContactAdmin = {
  readonly cle: string;
  readonly texte_fr: string;
  readonly texte_en: string;
  readonly telephone: string | null;
};

export async function contactsAdmin(): Promise<ReadonlyArray<ContactAdmin>> {
  const lignes = await requete<{
    key: string;
    locale: string;
    value: { texte?: string; telephone?: string | null };
  }>("select key, locale, value from public.content_blocks where key = any($1)", [
    [...CLES_CONTACTS],
  ]);

  return CLES_CONTACTS.map((cle) => {
    const fr = lignes.find((l) => l.key === cle && l.locale === "fr")?.value ?? {};
    const en = lignes.find((l) => l.key === cle && l.locale === "en")?.value ?? {};
    return {
      cle,
      texte_fr: fr.texte ?? "",
      texte_en: en.texte ?? "",
      telephone: fr.telephone ?? null,
    };
  });
}

/** Le numéro est le même dans les deux langues : seul le libellé se traduit. */
export async function enregistrerContact(
  cle: CleContact,
  valeurs: {
    readonly texte_fr: string;
    readonly texte_en: string;
    readonly telephone: string | null;
  },
  par: string,
): Promise<void> {
  const charge = (texte: string): string =>
    JSON.stringify({ texte, telephone: valeurs.telephone });
  await requete(
    `insert into public.content_blocks (key, locale, value, updated_at, updated_by)
     values ($1, 'fr', $2::jsonb, now(), $4), ($1, 'en', $3::jsonb, now(), $4)
     on conflict (key, locale) do update
        set value = excluded.value, updated_at = now(), updated_by = excluded.updated_by`,
    [cle, charge(valeurs.texte_fr), charge(valeurs.texte_en), par],
  );
  await journaliser("contact.maj", cle);
}

// ---------------------------------------------------------------------- FAQ

export type FaqAdmin = {
  readonly id: string;
  readonly sort_order: number;
  readonly question_fr: string;
  readonly question_en: string;
  readonly answer_fr: string;
  readonly answer_en: string;
  readonly published: boolean;
};

export async function faqAdmin(): Promise<ReadonlyArray<FaqAdmin>> {
  return requete<FaqAdmin>(
    `select id, sort_order, question_fr, question_en, answer_fr, answer_en, published
       from public.faq order by sort_order, question_fr`,
  );
}

export type SaisieFaq = {
  readonly question_fr: string;
  readonly question_en: string;
  readonly answer_fr: string;
  readonly answer_en: string;
  readonly published: boolean;
  readonly sort_order: number;
};

export async function enregistrerFaq(id: string, saisie: SaisieFaq): Promise<void> {
  await requete(
    `update public.faq set question_fr = $2, question_en = $3,
            answer_fr = $4, answer_en = $5, published = $6, sort_order = $7
      where id = $1`,
    [
      id,
      saisie.question_fr,
      saisie.question_en,
      saisie.answer_fr,
      saisie.answer_en,
      saisie.published,
      saisie.sort_order,
    ],
  );
  await journaliser("faq.maj", id);
}

export async function ajouterFaq(saisie: SaisieFaq): Promise<string | undefined> {
  const ligne = await une<{ id: string }>(
    `insert into public.faq (sort_order, question_fr, question_en, answer_fr, answer_en, published)
     values ($1, $2, $3, $4, $5, $6) returning id`,
    [
      saisie.sort_order,
      saisie.question_fr,
      saisie.question_en,
      saisie.answer_fr,
      saisie.answer_en,
      saisie.published,
    ],
  );
  await journaliser("faq.ajout", ligne?.id ?? "");
  return ligne?.id;
}

export async function supprimerFaq(id: string): Promise<void> {
  await requete("delete from public.faq where id = $1", [id]);
  await journaliser("faq.suppression", id);
}

// -------------------------------------------------------------- Hébergements

export type SaisieHebergement = {
  readonly name: string;
  readonly distance_km: string | null;
  readonly price_hint: string | null;
  readonly url: string | null;
  readonly phone: string | null;
  readonly shuttle: boolean | null;
  readonly sort_order: number;
};

export type HebergementAdmin = SaisieHebergement & { readonly id: string };

export async function hebergementsAdmin(): Promise<ReadonlyArray<HebergementAdmin>> {
  return requete<HebergementAdmin>(
    `select id, name, distance_km::text as distance_km, price_hint, url, phone, shuttle, sort_order
       from public.accommodations order by sort_order, name`,
  );
}

export async function enregistrerHebergement(
  id: string,
  saisie: SaisieHebergement,
): Promise<void> {
  await requete(
    `update public.accommodations set name = $2, distance_km = $3::numeric, price_hint = $4,
            url = $5, phone = $6, shuttle = $7, sort_order = $8
      where id = $1`,
    [
      id,
      saisie.name,
      saisie.distance_km,
      saisie.price_hint,
      saisie.url,
      saisie.phone,
      saisie.shuttle,
      saisie.sort_order,
    ],
  );
  await journaliser("hebergement.maj", id);
}

export async function ajouterHebergement(
  saisie: SaisieHebergement,
): Promise<string | undefined> {
  const ligne = await une<{ id: string }>(
    `insert into public.accommodations (name, distance_km, price_hint, url, phone, shuttle, sort_order)
     values ($1, $2::numeric, $3, $4, $5, $6, $7) returning id`,
    [
      saisie.name,
      saisie.distance_km,
      saisie.price_hint,
      saisie.url,
      saisie.phone,
      saisie.shuttle,
      saisie.sort_order,
    ],
  );
  await journaliser("hebergement.ajout", ligne?.id ?? "");
  return ligne?.id;
}

export async function supprimerHebergement(id: string): Promise<void> {
  await requete("delete from public.accommodations where id = $1", [id]);
  await journaliser("hebergement.suppression", id);
}

// ------------------------------------------------------------------ Journée

/**
 * Date limite de réponse (question V1-02). La date du mariage n'est pas
 * éditable : elle est fixée par le brief §1 et sert de référence à tout le
 * reste (périodes, rappels, purges).
 */
export async function enregistrerDateLimite(date: string | null): Promise<void> {
  await requete(
    "update public.parametres set date_limite_reponse = $1::date, maj_le = now() where id = 1",
    [date],
  );
  await journaliser("date_limite.maj", date ?? "vide");
}

// ----------------------------------------------------------------- Journal

/**
 * Journal d'audit (brief §11). On y met l'action et sa cible, jamais
 * l'adresse de l'éditeur : le rôle suffit à comprendre, et le journal est
 * purgé au bout de trente jours.
 */
async function journaliser(action: string, cible: string): Promise<void> {
  await requete("insert into public.audit_log (role, action, target) values ('admin', $1, $2)", [
    action,
    cible,
  ]);
}

// ------------------------------------------------------- Reste à compléter

const EN_ATTENTE = (texte: string | null): boolean =>
  texte === null ||
  texte.trim() === "" ||
  texte.includes("[À COMPLÉTER]") ||
  texte.includes("[TO BE COMPLETED]");

/**
 * Nombre d'éléments encore vides, affiché en tête de l'écran : les mariés
 * savent d'un coup d'œil ce qu'il reste à écrire avant le faire-part.
 */
export async function resteACompleter(): Promise<number> {
  const [moments, blocs, contacts, questions, jour] = await Promise.all([
    requete<{ debut: string | null; place: string | null }>(
      `select to_char(starts_at, 'HH24:MI') as debut, place from public.moments`,
    ),
    blocsAdmin(),
    contactsAdmin(),
    requete<{ answer_fr: string; answer_en: string }>(
      "select answer_fr, answer_en from public.faq",
    ),
    une<{ date_limite_reponse: Date | null }>(
      "select date_limite_reponse from public.parametres where id = 1",
    ),
  ]);

  let reste = jour?.date_limite_reponse == null ? 1 : 0;
  for (const moment of moments) if (moment.debut === null) reste += 1;
  for (const bloc of blocs) {
    if (EN_ATTENTE(bloc.texte_fr) || EN_ATTENTE(bloc.texte_en)) reste += 1;
  }
  for (const contact of contacts) {
    // Un contact sans numéro est inutile : le bouton d'appel n'existerait pas.
    if (contact.telephone === null || EN_ATTENTE(contact.texte_fr)) reste += 1;
  }
  for (const question of questions) {
    if (EN_ATTENTE(question.answer_fr) || EN_ATTENTE(question.answer_en)) reste += 1;
  }
  return reste;
}
