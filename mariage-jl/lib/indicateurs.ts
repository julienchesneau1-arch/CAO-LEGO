import "server-only";
import { requete } from "./db";

/**
 * Indicateurs de réussite (brief §16), **sans traceur**.
 *
 * C'est la contrainte qui décide de tout ici : aucun script d'analyse,
 * aucun cookie de mesure, aucun appel vers un tiers. On ne mesure donc que
 * ce que la base sait déjà, parce qu'elle en a besoin pour fonctionner —
 * l'heure de première ouverture, l'heure d'une réponse, le nombre de
 * souvenirs. Rien n'est ajouté pour mesurer.
 *
 * Et ce qui n'est pas mesurable est **dit comme tel**, jamais approché :
 * un indicateur inventé serait pire qu'un indicateur absent, parce qu'il
 * serait lu comme un fait (règle 2 : ne jamais deviner).
 */
export type Indicateur = {
  readonly cle: string;
  /** Valeur mesurée, ou `undefined` si elle n'est pas mesurable sans traceur. */
  readonly valeur: number | undefined;
  /** Base du pourcentage, quand l'indicateur en est un. */
  readonly sur: number | undefined;
  readonly objectif: number;
  readonly unite: "pourcentage" | "nombre";
  /** Renseigné seulement quand `valeur` est indisponible. */
  readonly pourquoi?: string;
};

export type Indicateurs = {
  readonly liste: ReadonlyArray<Indicateur>;
  /** Médiane du délai ouverture → réponse, en secondes. */
  readonly delaiMedianS: number | undefined;
};

export async function indicateurs(): Promise<Indicateurs> {
  const [compteurs] = await requete<{
    foyers: number;
    ouverts: number;
    repondus: number;
    rapides: number;
    mesurables: number;
    souvenirs: number;
    emails_echoues: number;
  }>(
    `select
       (select count(*)::int from public.households where revoked_at is null) as foyers,
       (select count(*)::int from public.households where first_opened_at is not null) as ouverts,
       (select count(*)::int from public.rsvp) as repondus,
       /*
         « Réponse en moins de 2 minutes » : le délai entre la première
         ouverture de l'invitation et la réponse. Un foyer qui a répondu
         sans que l'ouverture ait été enregistrée n'entre dans aucun des
         deux comptes — il fausserait la proportion dans un sens comme dans
         l'autre.
       */
       (select count(*)::int from public.rsvp r
          join public.households h on h.id = r.household_id
         where h.first_opened_at is not null
           and r.submitted_at - h.first_opened_at <= interval '2 minutes') as rapides,
       (select count(*)::int from public.rsvp r
          join public.households h on h.id = r.household_id
         where h.first_opened_at is not null) as mesurables,
       (select count(*)::int from public.media where status = 'published') as souvenirs,
       (select count(*)::int from public.emails where statut = 'echec') as emails_echoues`,
  );

  const [delai] = await requete<{ median: string | null }>(
    `select extract(epoch from percentile_cont(0.5) within group (
              order by r.submitted_at - h.first_opened_at))::text as median
       from public.rsvp r
       join public.households h on h.id = r.household_id
      where h.first_opened_at is not null`,
  );

  const foyers = compteurs?.foyers ?? 0;
  const mesurables = compteurs?.mesurables ?? 0;
  const mediane = delai?.median === null || delai?.median === undefined ? undefined : Number(delai.median);

  return {
    delaiMedianS: mediane === undefined || Number.isNaN(mediane) ? undefined : Math.round(mediane),
    liste: [
      {
        cle: "ouverts",
        valeur: compteurs?.ouverts ?? 0,
        sur: foyers,
        objectif: 90,
        unite: "pourcentage",
      },
      {
        cle: "reponses",
        valeur: compteurs?.repondus ?? 0,
        sur: foyers,
        objectif: 85,
        unite: "pourcentage",
      },
      {
        cle: "rapides",
        valeur: compteurs?.rapides ?? 0,
        sur: mesurables,
        objectif: 80,
        unite: "pourcentage",
      },
      {
        cle: "souvenirs",
        valeur: compteurs?.souvenirs ?? 0,
        sur: undefined,
        objectif: 300,
        unite: "nombre",
      },
      {
        // Un e-mail passe en « echec » après cinq tentatives : celui-là, on
        // le sait. Un envoi de photo abandonné dans un téléphone, non — et
        // le savoir demanderait de faire remonter l'échec, donc de tracer.
        cle: "emails_echoues",
        valeur: compteurs?.emails_echoues ?? 0,
        sur: undefined,
        objectif: 0,
        unite: "nombre",
      },
      {
        cle: "envois_echoues",
        valeur: undefined,
        sur: undefined,
        objectif: 0,
        unite: "nombre",
        pourquoi: "sans_traceur",
      },
      {
        cle: "questions",
        valeur: undefined,
        sur: undefined,
        objectif: 0,
        unite: "nombre",
        pourquoi: "hors_application",
      },
      {
        cle: "interventions",
        valeur: undefined,
        sur: undefined,
        objectif: 0,
        unite: "nombre",
        pourquoi: "hors_application",
      },
      {
        cle: "incidents",
        valeur: undefined,
        sur: undefined,
        objectif: 0,
        unite: "nombre",
        pourquoi: "hors_application",
      },
    ],
  };
}

/** Pourcentage entier, ou `undefined` quand la base est vide. */
export function pourcentage(valeur: number, sur: number): number | undefined {
  return sur === 0 ? undefined : Math.round((valeur / sur) * 100);
}

/**
 * L'objectif est-il atteint ? `undefined` quand on ne peut pas le dire —
 * base vide ou indicateur non mesurable. Un « non atteint » affiché sur
 * zéro foyer serait un mensonge par défaut.
 */
export function atteint(indicateur: Indicateur): boolean | undefined {
  if (indicateur.valeur === undefined) return undefined;
  if (indicateur.unite === "nombre") {
    return indicateur.objectif === 0
      ? indicateur.valeur === 0
      : indicateur.valeur >= indicateur.objectif;
  }
  const part = pourcentage(indicateur.valeur, indicateur.sur ?? 0);
  return part === undefined ? undefined : part >= indicateur.objectif;
}
