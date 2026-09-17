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
    /**
     * Sans ce gestionnaire, une connexion coupée par le serveur de base
     * (redémarrage de Supabase, pgBouncer qui recycle, bascule réseau) émet un
     * événement « error » non traité et **arrête le processus Node**. Le site
     * tomberait pour une simple coupure passagère : ici on la journalise et le
     * pool ouvre une nouvelle connexion à la requête suivante.
     */
    pool.on("error", (erreur) => {
      console.error("[base] connexion inactive perdue :", erreur.message);
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

/**
 * Transaction : une réponse d'invité touche plusieurs tables (présence par
 * moment, régimes, allergies). Elle est enregistrée entièrement, ou pas du
 * tout — jamais à moitié.
 */
export async function transaction<T>(
  travail: (executer: <L extends Record<string, unknown>>(
    sql: string,
    valeurs?: ReadonlyArray<unknown>,
  ) => Promise<L[]>) => Promise<T>,
): Promise<T> {
  const client = await obtenirPool().connect();
  try {
    await client.query("begin");
    const resultat = await travail(async (sql, valeurs = []) => {
      const r = await client.query(sql, valeurs as unknown[]);
      return r.rows as never;
    });
    await client.query("commit");
    return resultat;
  } catch (erreur) {
    await client.query("rollback");
    throw erreur;
  } finally {
    client.release();
  }
}
