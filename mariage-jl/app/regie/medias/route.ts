import type { NextRequest } from "next/server";
import { z } from "zod";
import { redirection } from "@/lib/http";
import { masquer, resoudreSignalement } from "@/lib/medias";
import { exigerRegie } from "@/lib/regie";

const Saisie = z.object({
  media: z.string().uuid().optional(),
  signalement: z.string().uuid().optional(),
  masquer: z.enum(["0", "1"]).optional(),
});

/** Modération en un tap (brief §9) : masquer, rendre visible, classer. */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerRegie()) === undefined) return redirection("/regie");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    media: donnees.get("media")?.toString() || undefined,
    signalement: donnees.get("signalement")?.toString() || undefined,
    masquer: donnees.get("masquer")?.toString() || undefined,
  });
  if (!saisie.success) return redirection("/regie?etat=erreur");

  if (saisie.data.media !== undefined && saisie.data.masquer !== undefined) {
    await masquer(saisie.data.media, saisie.data.masquer === "1");
  }
  if (saisie.data.signalement !== undefined) {
    await resoudreSignalement(saisie.data.signalement);
  }
  return redirection("/regie?etat=modere#souvenirs");
}
