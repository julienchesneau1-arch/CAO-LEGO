import type { NextRequest } from "next/server";
import { z } from "zod";
import { foyerCourant } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { basculerSignal } from "@/lib/medias";

const Saisie = z.object({ media: z.string().uuid(), retour: z.string().max(200) });

/**
 * « J'aime » privé : il sert au tri (brief §8.7) et n'est jamais affiché en
 * nombre (§17). Aucun message de confirmation : le cœur change d'état, c'est
 * tout ce qu'on doit à l'invité.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/photos?etat=sans_foyer");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    media: donnees.get("media"),
    retour: donnees.get("retour")?.toString() ?? "/photos",
  });
  if (!saisie.success) return redirection("/photos?etat=erreur");

  await basculerSignal(saisie.data.media, foyer.id);
  // On revient exactement où l'invité était, filtre compris.
  const retour = saisie.data.retour.startsWith("/photos") ? saisie.data.retour : "/photos";
  return redirection(retour);
}
