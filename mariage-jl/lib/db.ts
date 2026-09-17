import "server-only";
import { Pool } from "pg";
import { urlBase } from "./env";

/**
 * Accès à Postgres depuis le serveur uniquement (brief §11, docs/PLAN.md §3.4).
 * Aucun invité ne détient de clé : toutes ses lectures passent par ici, et
 * chaque requête est explicitement filtrée par foyer.
 *
 * En production, l'URL est celle de Supabase (Europe) ; la RLS reste active
 * comme seconde barrière pour les rôles admin et régie.
 */
let pool: Pool | undefined;

function obtenirPool(): Pool {
  if (pool === undefined) {
    pool = new Pool({
      connectionString: urlBase(),
      max: 8,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
    });
  }
  return pool;
}

export async function requete<T extends Record<string, unknown>>(
  sql: string,
  valeurs: ReadonlyArray<unknown> = [],
): Promise<T[]> {
  const resultat = await obtenirPool().query<T>(sql, valeurs as unknown[]);
  return resultat.rows;
}

export async function une<T extends Record<string, unknown>>(
  sql: string,
  valeurs: ReadonlyArray<unknown> = [],
): Promise<T | undefined> {
  const lignes = await requete<T>(sql, valeurs);
  return lignes[0];
}
