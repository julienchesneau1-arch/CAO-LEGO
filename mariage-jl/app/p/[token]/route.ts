import { COOKIE_FOYER, DUREE_COOKIE_S, signerSession } from "@/lib/acces";
import { enProduction, secretCookie } from "@/lib/env";
import { redirection } from "@/lib/http";
import { foyerParLienPartage, tentativeAutorisee } from "@/lib/foyer";

/**
 * Lien de partage du foyer (brief §6, arbitrage C10) : le conjoint ou un
 * proche ouvre la même invitation. C'est aussi le mécanisme « un proche
 * répond pour moi » — il n'y en a qu'un.
 */
export async function GET(
  _requete: Request,
  contexte: { params: Promise<{ token: string }> },
): Promise<Response> {
  const { token } = await contexte.params;

  if (!(await tentativeAutorisee("partage", "1 hour", 60))) {
    return redirection("/retrouver?etat=debit");
  }

  const foyer = await foyerParLienPartage(token);
  if (foyer === undefined) {
    return redirection("/retrouver?etat=expire");
  }

  const reponse = redirection("/");
  reponse.cookies.set({
    name: COOKIE_FOYER,
    value: signerSession({ foyer: foyer.id, emis: Math.floor(Date.now() / 1000) }, secretCookie()),
    httpOnly: true,
    sameSite: "lax",
    secure: enProduction(),
    path: "/",
    maxAge: DUREE_COOKIE_S,
  });
  return reponse;
}
