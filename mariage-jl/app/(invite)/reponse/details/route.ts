import type { NextRequest } from "next/server";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { moments } from "@/lib/moments";
import { REGIMES, SchemaDetails, enregistrerDetails, reponseVerrouillee } from "@/lib/rsvp";

/** Version du texte de consentement : tracée avec chaque allergie (§11). */
export const VERSION_CONSENTEMENT = "allergies-2026-09-17";

const texte = (donnees: FormData, cle: string): string => {
  const valeur = donnees.get(cle);
  return typeof valeur === "string" ? valeur : "";
};

/**
 * Étapes 2 à 4 (brief §8.2) : présences, menus, régimes, allergies, puis les
 * champs facultatifs. Un seul envoi, une seule transaction.
 */
export async function POST(requeteHttp: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/reponse?etat=inconnu");
  if (await reponseVerrouillee()) return redirection("/reponse?etat=verrouille");
  if (!(await tentativeAutorisee("reponse-details", "1 hour", 60))) {
    return redirection("/reponse?etat=debit");
  }

  const donnees = await requeteHttp.formData();
  const identifiants = donnees.getAll("invite").filter((v): v is string => typeof v === "string");
  const momentsConnus = (await moments()).map((moment) => moment.id);

  const presences: Record<string, string[]> = {};
  const menus: Record<string, string> = {};
  const regimes: Record<string, string[]> = {};
  const allergies: Record<string, string> = {};

  for (const invite of identifiants) {
    // Sans case cochée, « Préciser » n'a pas été ouvert : l'invité est présent
    // partout, ce qui est le cas de très loin le plus fréquent.
    const precise = donnees.get(`precise-${invite}`) === "1";
    presences[invite] = precise
      ? donnees.getAll(`presence-${invite}`).filter((v): v is string => typeof v === "string")
      : [...momentsConnus];
    menus[invite] = texte(donnees, `menu-${invite}`);
    regimes[invite] = donnees
      .getAll(`regime-${invite}`)
      .filter((v): v is string => typeof v === "string" && (REGIMES as readonly string[]).includes(v));
    allergies[invite] = texte(donnees, `allergies-${invite}`);
  }

  const saisie = SchemaDetails.safeParse({
    presences,
    menus,
    regimes,
    allergies,
    consentementAllergies: donnees.get("consentement-allergies") === "1",
    versionConsentement: VERSION_CONSENTEMENT,
    chanson: texte(donnees, "chanson"),
    message: texte(donnees, "message"),
    hebergement: texte(donnees, "hebergement"),
    transport: texte(donnees, "transport"),
  });
  if (!saisie.success) return redirection("/reponse?etat=erreur");

  await enregistrerDetails(foyer.id, saisie.data, momentsConnus);
  return redirection("/reponse?etat=enregistre");
}
