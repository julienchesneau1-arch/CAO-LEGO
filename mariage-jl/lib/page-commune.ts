import "server-only";
import { cookies } from "next/headers";
import { COOKIE_LANGUE, LANGUE_DEFAUT, dictionnaire, estLangue, type Dictionnaire, type Langue } from "./i18n";

/** Langue et dictionnaire de la requête courante, en une ligne par page. */
export async function langueEtTextes(): Promise<{ langue: Langue; t: Dictionnaire }> {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeur) ? valeur : LANGUE_DEFAUT;
  return { langue, t: dictionnaire(langue) };
}
