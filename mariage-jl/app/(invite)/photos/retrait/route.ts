import type { NextRequest } from "next/server";
import { z } from "zod";
import { foyerCourant } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { demanderRetrait } from "@/lib/medias";

const Saisie = z.object({
  media: z.string().uuid(),
  raison: z.string().max(500).nullable(),
});

/**
 * Demande de retrait (brief §8.7, « en un tap »). Elle masque le média
 * **immédiatement** : faire attendre quelqu'un qui demande le retrait d'une
 * photo où il apparaît serait le contraire de ce que le brief promet.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/photos?etat=sans_foyer");

  const donnees = await requete.formData();
  const brute = donnees.get("raison")?.toString().trim() ?? "";
  const saisie = Saisie.safeParse({
    media: donnees.get("media"),
    raison: brute === "" ? null : brute,
  });
  if (!saisie.success) return redirection("/photos?etat=erreur");

  const fait = await demanderRetrait(saisie.data.media, foyer.id, saisie.data.raison);
  return redirection(`/photos?etat=${fait ? "retire" : "erreur"}`);
}
