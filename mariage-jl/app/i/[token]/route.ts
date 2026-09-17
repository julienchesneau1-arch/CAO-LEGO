import { type NextRequest } from "next/server";
import { COOKIE_FOYER, DUREE_COOKIE_S, signerSession } from "@/lib/acces";
import { enProduction, secretCookie } from "@/lib/env";
import { redirection } from "@/lib/http";
import { foyerParJeton, marquerOuverture, tentativeAutorisee } from "@/lib/foyer";
import { COOKIE_LANGUE, estLangue } from "@/lib/i18n";

/**
 * Ouverture d'une invitation depuis le QR code du faire-part (brief §6).
 * Le jeton n'est jamais conservé : il sert une fois, pour poser un cookie
 * signé. L'appareil est ensuite reconnu sans rien demander à l'invité.
 */
export async function GET(
  requete: NextRequest,
  contexte: { params: Promise<{ token: string }> },
): Promise<Response> {
  const { token } = await contexte.params;

  // Un QR ne se devine pas, mais le point d'entrée se protège quand même.
  if (!(await tentativeAutorisee("invitation", "1 hour", 60))) {
    return redirection("/retrouver?etat=debit");
  }

  const foyer = await foyerParJeton(token);
  if (foyer === undefined) {
    return redirection("/retrouver?etat=inconnu");
  }

  await marquerOuverture(foyer.id);

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

  // Langue du foyer, seulement si l'invité n'a pas déjà choisi.
  const dejaChoisie = requete.cookies.get(COOKIE_LANGUE)?.value;
  if (!estLangue(dejaChoisie) && estLangue(foyer.lang_default)) {
    reponse.cookies.set({
      name: COOKIE_LANGUE,
      value: foyer.lang_default,
      sameSite: "lax",
      secure: enProduction(),
      path: "/",
      maxAge: DUREE_COOKIE_S,
    });
  }

  return reponse;
}
