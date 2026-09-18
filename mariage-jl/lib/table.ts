import "server-only";
import { requete, une } from "./db";

/**
 * Plan de table (brief §0 bis, « recherche de son nom, table » —
 * indispensable). Ce que le brief **coupe** : la présentation des voisins de
 * table. On donne donc le numéro de table et les prénoms qui y sont, rien de
 * plus : pas de trombinoscope, pas de « qui est qui ».
 */
export type Table = {
  readonly id: string;
  readonly label: string;
  readonly capacity: number | null;
  readonly sort_order: number;
};

export type Place = {
  readonly guest_id: string;
  readonly prenom: string;
  readonly table_id: string | null;
  readonly table_label: string | null;
  readonly household_id: string;
};

export async function tables(): Promise<ReadonlyArray<Table>> {
  return requete<Table>(
    "select id, label, capacity, sort_order from public.seating_tables order by sort_order, label",
  );
}

/** Les places d'un foyer : ce que l'invité vient chercher. */
export async function placesDuFoyer(foyer: string): Promise<ReadonlyArray<Place>> {
  return requete<Place>(
    `select g.id as guest_id, g.first_name as prenom, a.table_id,
            t.label as table_label, g.household_id
       from public.guests g
       left join public.seating_assign a on a.guest_id = g.id
       left join public.seating_tables t on t.id = a.table_id
      where g.household_id = $1
      order by g.sort_order, g.first_name`,
    [foyer],
  );
}

/** Les prénoms d'une table, pour savoir avec qui on est assis. */
export async function prenomsDeLaTable(tableId: string): Promise<ReadonlyArray<string>> {
  const lignes = await requete<{ prenom: string }>(
    `select g.first_name as prenom
       from public.seating_assign a
       join public.guests g on g.id = a.guest_id
      where a.table_id = $1
      order by g.first_name`,
    [tableId],
  );
  return lignes.map((ligne) => ligne.prenom);
}

/**
 * Recherche par prénom (brief §0 bis). Insensible à la casse et aux accents :
 * « Chloe » trouve « Chloé ».
 *
 * Elle se fait **côté serveur**, avec deux caractères minimum et vingt
 * résultats au plus. La recherche de la FAQ, elle, tourne dans le téléphone,
 * mais la liste des invités n'est pas de la même nature : l'envoyer en entier
 * à quiconque détient une invitation reviendrait à publier le carnet
 * d'adresses du mariage (§11). Le repli hors ligne est le papier — les cartes
 * de table portent le plan (§10).
 *
 * Elle ne renvoie **que** le prénom et la table : chercher « Marie » ne doit
 * pas révéler son foyer, sa réponse ou son régime.
 */
export async function chercherUnePlace(
  terme: string,
): Promise<ReadonlyArray<{ readonly prenom: string; readonly table: string | null }>> {
  const propre = terme.trim();
  if (propre.length < 2) return [];
  return requete<{ prenom: string; table: string | null }>(
    `select g.first_name as prenom, t.label as table
       from public.guests g
       left join public.seating_assign a on a.guest_id = g.id
       left join public.seating_tables t on t.id = a.table_id
      where jl.sans_accents(g.first_name) like '%' || jl.sans_accents($1) || '%'
      order by g.first_name
      limit 20`,
    [propre],
  );
}

// -------------------------------------------------------------- Côté admin

export async function creerTable(
  label: string,
  capacite: number | null,
  ordre: number,
): Promise<string | undefined> {
  const ligne = await une<{ id: string }>(
    `insert into public.seating_tables (label, capacity, sort_order)
     values ($1, $2, $3)
     on conflict (label) do update set capacity = excluded.capacity,
                                       sort_order = excluded.sort_order
     returning id`,
    [label, capacite, ordre],
  );
  return ligne?.id;
}

export async function supprimerTable(id: string): Promise<void> {
  await requete("delete from public.seating_tables where id = $1", [id]);
}

/** Affecter une personne, ou la retirer de toute table si `tableId` est nul. */
export async function affecter(guestId: string, tableId: string | null): Promise<void> {
  if (tableId === null) {
    await requete("delete from public.seating_assign where guest_id = $1", [guestId]);
    return;
  }
  await requete(
    `insert into public.seating_assign (guest_id, table_id) values ($1, $2)
     on conflict (guest_id) do update set table_id = excluded.table_id`,
    [guestId, tableId],
  );
}

export type PlaceAdmin = Place & { readonly foyer: string };

/** Tout le monde, avec sa table : l'écran des mariés en a besoin d'un coup. */
export async function toutesLesPlaces(): Promise<ReadonlyArray<PlaceAdmin>> {
  return requete<PlaceAdmin>(
    `select g.id as guest_id, g.first_name as prenom, a.table_id,
            t.label as table_label, g.household_id, h.label_public as foyer
       from public.guests g
       join public.households h on h.id = g.household_id
       left join public.seating_assign a on a.guest_id = g.id
       left join public.seating_tables t on t.id = a.table_id
      order by h.label_public, g.sort_order, g.first_name`,
  );
}
