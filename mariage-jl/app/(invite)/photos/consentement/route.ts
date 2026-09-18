import type { NextRequest } from "next/server";
import { z } from "zod";
import { foyerCourant } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { accorderConsentementMedias, retirerConsentementMedias } from "@/lib/medias";

const Saisie = z.object({ visibilite: z.enum(["invites", "maries"]) });

/** Consentement au partage, donné ou retiré (brief §8.7). */
export async function POST(requete: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/photos?etat=sans_foyer");

  const donnees = await requete.formData();
  if (donnees.get("retirer") === "1") {
    await retirerConsentementMedias(foyer.id);
    return redirection("/photos/envoyer?etat=retire");
  }

  const saisie = Saisie.safeParse({ visibilite: donnees.get("visibilite") });
  if (!saisie.success) return redirection("/photos/envoyer?etat=erreur");
  await accorderConsentementMedias(foyer.id, saisie.data.visibilite);
  return redirection("/photos/envoyer?etat=consenti");
}
