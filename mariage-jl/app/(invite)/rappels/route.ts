import type { NextRequest } from "next/server";
import { headers } from "next/headers";
import { z } from "zod";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { activerRappels, desactiverRappels, envoyerConfirmation } from "@/lib/rappels";

/**
 * Activation ou arrêt des rappels (brief V2 et §11 : opt-in explicite).
 * L'arrêt ne demande aucune confirmation : c'est un droit, pas une négociation.
 */
const Saisie = z.object({
  action: z.enum(["activer", "arreter"]),
  email: z.string().email().max(200).optional(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/reponse?etat=inconnu");
  if (!(await tentativeAutorisee("rappels", "1 hour", 20))) {
    return redirection("/reponse?etat=debit");
  }

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    action: donnees.get("action"),
    email: donnees.get("email") ?? undefined,
  });
  if (!saisie.success) return redirection("/reponse?etat=erreur");

  if (saisie.data.action === "arreter") {
    await desactiverRappels(foyer.id);
    return redirection("/reponse?etat=rappels_arretes");
  }

  if (saisie.data.email === undefined) return redirection("/reponse?etat=erreur");

  const { jetonDesinscription } = await activerRappels(foyer.id, saisie.data.email);
  const entetes = await headers();
  const hote = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "";
  const protocole = entetes.get("x-forwarded-proto") ?? "https";
  await envoyerConfirmation(
    saisie.data.email,
    `${protocole}://${hote}/desabonner/${jetonDesinscription}`,
  );

  return redirection("/reponse?etat=rappels_actives");
}
