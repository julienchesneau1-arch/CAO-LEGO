import { NextResponse } from "next/server";

/**
 * Redirection à chemin relatif. `NextResponse.redirect` exige une URL absolue
 * et réécrit l'hôte : derrière un reverse proxy, cela renvoie l'invité vers
 * l'hôte interne et fait perdre le cookie au passage. Un `Location` relatif
 * est résolu par le navigateur contre l'URL courante : rien à devineur.
 */
export function redirection(chemin: string, statut: 303 | 307 = 303): NextResponse {
  return new NextResponse(null, { status: statut, headers: { location: chemin } });
}
