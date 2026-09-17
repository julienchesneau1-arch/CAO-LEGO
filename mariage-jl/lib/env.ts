import { z } from "zod";

/**
 * Variables d'environnement validées une seule fois (brief §5 : zod pour les
 * formulaires, l'API et l'environnement). Rien n'est deviné : une variable
 * absente donne une erreur explicite au moment où on en a besoin, pas un
 * comportement silencieux.
 */
const Schema = z.object({
  JL_DATABASE_URL: z.string().min(1).optional(),
  JL_COOKIE_SECRET: z.string().min(32).optional(),
  JL_ALLOW_CLOCK_OVERRIDE: z.enum(["0", "1"]).default("0"),
  JL_VERSION: z.string().default("v1-dev"),
  JL_FILM_URL: z.string().optional(),
  // Clé publique de « La promesse » : elle n'a rien de secret, c'est la clé
  // privée — imprimée, conservée hors ligne — qui ouvre les vœux en 2029.
  JL_PROMESSE_CLE_PUBLIQUE: z.string().optional(),
  JL_FILM_POSTER_URL: z.string().optional(),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
});

export type Env = z.infer<typeof Schema>;

let cache: Env | undefined;

export function env(): Env {
  if (cache === undefined) {
    const resultat = Schema.safeParse(process.env);
    if (!resultat.success) {
      throw new Error(`Environnement invalide : ${resultat.error.message}`);
    }
    cache = resultat.data;
  }
  return cache;
}

export function enProduction(): boolean {
  return env().NODE_ENV === "production";
}

/** Secret de signature des cookies. En production, son absence est fatale. */
export function secretCookie(): string {
  const { JL_COOKIE_SECRET } = env();
  if (JL_COOKIE_SECRET !== undefined) return JL_COOKIE_SECRET;
  if (enProduction()) {
    throw new Error("JL_COOKIE_SECRET est obligatoire en production.");
  }
  // Développement seulement : clé fixe, bruyante, jamais utilisable en ligne.
  return "developpement-uniquement-clef-non-secrete-32+";
}

export function urlBase(): string {
  const { JL_DATABASE_URL } = env();
  if (JL_DATABASE_URL === undefined) {
    throw new Error("JL_DATABASE_URL est absent : voir .env.example.");
  }
  return JL_DATABASE_URL;
}
