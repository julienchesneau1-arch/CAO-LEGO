import type { NextRequest } from "next/server";
import {
  COOKIE_ADMIN,
  DUREE_SESSION_S,
  consommerLienMagique,
  signerSessionAdmin,
} from "@/lib/admin";
import { enProduction } from "@/lib/env";
import { tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";

/**
 * Entrée par lien magique (brief §6). Le jeton est à usage unique et vérifié
 * en base ; il n'ouvre une session que s'il est encore valide et si le compte
 * n'a pas été révoqué entre-temps.
 */
export async function GET(requete: NextRequest): Promise<Response> {
  const jeton = requete.nextUrl.searchParams.get("jeton");
  if (jeton === null || !(await tentativeAutorisee("admin-entrer", "1 hour", 20))) {
    return redirection("/admin");
  }

  const session = await consommerLienMagique(jeton);
  if (session === undefined) return redirection("/admin");

  const reponse = redirection("/admin");
  reponse.cookies.set({
    name: COOKIE_ADMIN,
    value: signerSessionAdmin(session),
    httpOnly: true,
    sameSite: "lax",
    secure: enProduction(),
    path: "/",
    maxAge: DUREE_SESSION_S,
  });
  return reponse;
}
