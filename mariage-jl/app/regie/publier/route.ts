import type { NextRequest } from "next/server";
import { z } from "zod";
import { publierAnnonce } from "@/lib/annonces";
import { redirection } from "@/lib/http";
import { dictionnaire } from "@/lib/i18n";
import { notifier, pushConfigure } from "@/lib/push";
import { exigerRegie } from "@/lib/regie";

const MODELES = ["ceremonie", "cocktail", "diner", "navette"] as const;
type Modele = (typeof MODELES)[number];

const estModele = (valeur: string): valeur is Modele =>
  (MODELES as readonly string[]).includes(valeur);

const Libre = z.object({ texte: z.string().min(2).max(500) });

/**
 * Annonce publiée par la régie (brief §9). Un modèle est désigné par sa clé :
 * les deux langues viennent alors des dictionnaires. Une annonce libre part
 * telle quelle dans les deux langues — traduire à la volée un soir de fête
 * n'est pas réaliste, et l'écran le dit avant d'envoyer.
 *
 * Une annonce de la régie **notifie** les abonnés : le jour J, c'est le
 * but. Avant le jour J, c'est l'écran des mariés qui publie, avec sa case.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerRegie()) === undefined) return redirection("/regie");

  const donnees = await requete.formData();
  const modele = donnees.get("modele")?.toString() ?? "";

  let texteFr: string;
  let texteEn: string;
  if (modele !== "" && estModele(modele)) {
    texteFr = dictionnaire("fr").regie[`modele_${modele}`];
    texteEn = dictionnaire("en").regie[`modele_${modele}`];
  } else {
    const saisie = Libre.safeParse({ texte: donnees.get("texte") });
    if (!saisie.success) return redirection("/regie?etat=erreur");
    texteFr = saisie.data.texte;
    texteEn = saisie.data.texte;
  }

  await publierAnnonce(texteFr, texteEn, "regie");
  if (pushConfigure()) await notifier("Julien & Lauriane", texteFr, "/annonces");
  return redirection("/regie?etat=publiee");
}
