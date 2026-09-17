import type { NextRequest } from "next/server";
import { z } from "zod";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { STATUTS, enregistrerStatut, reponseVerrouillee } from "@/lib/rsvp";

/**
 * Étape 1 de la réponse (brief §8.2) : un tap suffit, et il est enregistré
 * immédiatement. Si l'invité s'arrête là, l'essentiel est dit.
 */
const Saisie = z.object({ statut: z.enum(STATUTS) });

export async function POST(requeteHttp: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/reponse?etat=inconnu");
  if (await reponseVerrouillee()) return redirection("/reponse?etat=verrouille");
  if (!(await tentativeAutorisee("reponse", "1 hour", 60))) {
    return redirection("/reponse?etat=debit");
  }

  const donnees = await requeteHttp.formData();
  const saisie = Saisie.safeParse({ statut: donnees.get("statut") });
  if (!saisie.success) return redirection("/reponse?etat=erreur");

  await enregistrerStatut(foyer.id, saisie.data.statut);
  return redirection("/reponse?etat=enregistre");
}
