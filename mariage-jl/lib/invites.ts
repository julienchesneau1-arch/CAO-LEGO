import "server-only";
import { empreinte, genererCodeSecours, genererJeton } from "./acces";
import { requete, transaction, une } from "./db";
import type { LigneFoyer } from "./csv";
import type { FoyerAImprimer } from "./planche-qr";

export type FoyerAdmin = {
  readonly id: string;
  readonly label_public: string;
  readonly lang_default: string;
  readonly invites: number;
  readonly statut: string | null;
  readonly first_opened_at: Date | null;
  readonly revoked_at: Date | null;
};

/** Liste des foyers pour l'écran « Invités » (brief §14). */
export async function listerFoyers(): Promise<ReadonlyArray<FoyerAdmin>> {
  return requete<FoyerAdmin>(
    `select h.id, h.label_public, h.lang_default, h.first_opened_at, h.revoked_at,
            (select count(*)::int from public.guests g where g.household_id = h.id) as invites,
            (select r.status from public.rsvp r where r.household_id = h.id) as statut
       from public.households h
      order by h.label_public`,
  );
}

export type Tableau = {
  readonly foyers: number;
  readonly ouverts: number;
  readonly oui: number;
  readonly non: number;
  readonly peutetre: number;
  readonly sansReponse: number;
  readonly invites: number;
  readonly allergies: number;
  readonly presencesParMoment: ReadonlyArray<{ moment: string; presents: number }>;
  readonly regimes: ReadonlyArray<{ regime: string; personnes: number }>;
};

/** Indicateurs du tableau de bord (brief §14 et §16). Aucun calcul côté client. */
export async function tableauDeBord(): Promise<Tableau> {
  const [compteurs] = await requete<{
    foyers: number;
    ouverts: number;
    oui: number;
    non: number;
    peutetre: number;
    invites: number;
    allergies: number;
  }>(
    `select
       (select count(*)::int from public.households where revoked_at is null) as foyers,
       (select count(*)::int from public.households where first_opened_at is not null) as ouverts,
       (select count(*)::int from public.rsvp where status = 'yes') as oui,
       (select count(*)::int from public.rsvp where status = 'no') as non,
       (select count(*)::int from public.rsvp where status = 'maybe') as peutetre,
       (select count(*)::int from public.guests) as invites,
       (select count(*)::int from public.health_allergies) as allergies`,
  );

  const presences = await requete<{ moment: string; presents: number }>(
    `select m.id as moment,
            count(*) filter (where a.attending)::int as presents
       from public.moments m
       left join public.rsvp_attendance a on a.moment_id = m.id
      group by m.id order by m.id`,
  );

  const regimes = await requete<{ regime: string; personnes: number }>(
    `select regime, count(*)::int as personnes
       from public.guests, unnest(diet_flags) as regime
      group by regime order by regime`,
  );

  const total = compteurs?.foyers ?? 0;
  const repondus = (compteurs?.oui ?? 0) + (compteurs?.non ?? 0) + (compteurs?.peutetre ?? 0);
  return {
    foyers: total,
    ouverts: compteurs?.ouverts ?? 0,
    oui: compteurs?.oui ?? 0,
    non: compteurs?.non ?? 0,
    peutetre: compteurs?.peutetre ?? 0,
    sansReponse: Math.max(0, total - repondus),
    invites: compteurs?.invites ?? 0,
    allergies: compteurs?.allergies ?? 0,
    presencesParMoment: presences,
    regimes,
  };
}

/**
 * Création de foyers. Les jetons et les codes de secours ne sont **jamais
 * stockés en clair** : ils sont renvoyés une seule fois, pour la planche QR,
 * puis oubliés. C'est la raison pour laquelle l'import produit directement
 * le PDF à imprimer (brief §6 et §11).
 */
export async function creerFoyers(
  lignes: ReadonlyArray<LigneFoyer>,
): Promise<ReadonlyArray<FoyerAImprimer>> {
  return transaction(async (executer) => {
    const impressions: FoyerAImprimer[] = [];
    for (const ligne of lignes) {
      const jeton = genererJeton();
      const code = genererCodeSecours();
      const [cree] = await executer<{ id: string }>(
        `insert into public.households (label_public, token_sha256, backup_code_sha256, lang_default)
         values ($1, $2, $3, $4) returning id`,
        [ligne.foyer, empreinte(jeton), empreinte(code), ligne.langue],
      );
      for (const [index, prenom] of ligne.invites.entries()) {
        await executer(
          `insert into public.guests (household_id, first_name, sort_order) values ($1, $2, $3)`,
          [cree?.id, prenom, index],
        );
      }
      impressions.push({ label: ligne.foyer, jeton, code });
    }
    return impressions;
  });
}

/**
 * Régénère les accès pour réimprimer une planche. Les anciens QR et les
 * anciens codes cessent aussitôt de fonctionner : c'est le prix de ne jamais
 * conserver un jeton en clair, et l'écran l'annonce avant d'agir.
 */
export async function regenererAcces(): Promise<ReadonlyArray<FoyerAImprimer>> {
  return transaction(async (executer) => {
    const foyers = await executer<{ id: string; label_public: string }>(
      "select id, label_public from public.households where revoked_at is null order by label_public",
    );
    const impressions: FoyerAImprimer[] = [];
    for (const foyer of foyers) {
      const jeton = genererJeton();
      const code = genererCodeSecours();
      await executer(
        `update public.households set token_sha256 = $2, backup_code_sha256 = $3 where id = $1`,
        [foyer.id, empreinte(jeton), empreinte(code)],
      );
      impressions.push({ label: foyer.label_public, jeton, code });
    }
    return impressions;
  });
}

export async function revoquerFoyer(id: string): Promise<void> {
  await une("update public.households set revoked_at = now() where id = $1", [id]);
}
