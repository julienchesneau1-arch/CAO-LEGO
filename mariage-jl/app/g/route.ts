import { COOKIE_GENERIQUE, DUREE_COOKIE_S } from "@/lib/acces";
import { enProduction } from "@/lib/env";
import { redirection } from "@/lib/http";

/**
 * QR générique des cartes de table et des affiches (brief §6) : accès au
 * programme, aux infos et à la galerie, sans aucune donnée nominative.
 */
export function GET(): Response {
  const reponse = redirection("/");
  reponse.cookies.set({
    name: COOKIE_GENERIQUE,
    value: "1",
    sameSite: "lax",
    secure: enProduction(),
    path: "/",
    maxAge: DUREE_COOKIE_S,
  });
  return reponse;
}
