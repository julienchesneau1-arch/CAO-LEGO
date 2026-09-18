/**
 * Valeurs partagées des parcours Playwright. Ce jeton n'est pas un secret :
 * il n'existe que dans la base jetable des tests.
 */
export const BASE_E2E = "jl_e2e";
export const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
export const URL_E2E = new URL(`/${BASE_E2E}`, URL_ADMIN).href;

export const FOYER = {
  label: "Foyer d'essai Playwright",
  jeton: "essai2playwright3foyer4reconnu567",
  code: "TEST42",
  invite: "Camille",
} as const;

/** Même port que `playwright.config.ts` : utile pour ouvrir un second navigateur. */
export const BASE_URL = "http://127.0.0.1:3220";

/** Dossier jetable des souvenirs envoyés par les parcours. */
export const DOSSIER_MEDIAS = "/tmp/jl-e2e-medias";
