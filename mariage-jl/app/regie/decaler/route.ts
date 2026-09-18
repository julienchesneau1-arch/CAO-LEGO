import type { NextRequest } from "next/server";
import { z } from "zod";
import { redirection } from "@/lib/http";
import { annulerDecalages, decalerDepuis, exigerRegie } from "@/lib/regie";

/**
 * Décalage d'un moment (brief §9). Le pas est borné : ±120 minutes suffisent
 * à une journée qui glisse, et une valeur absurde saisie d'un pouce pressé ne
 * doit pas envoyer le dîner au lendemain.
 */
const Saisie = z.object({
  moment: z.enum(["01", "02", "03", "04", "05"]),
  minutes: z.number().int().min(-120).max(120).refine((v) => v !== 0),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerRegie()) === undefined) return redirection("/regie");

  const donnees = await requete.formData();
  if (donnees.get("remise") === "1") {
    await annulerDecalages();
    return redirection("/regie?etat=remis");
  }

  const saisie = Saisie.safeParse({
    moment: donnees.get("moment"),
    minutes: Number(donnees.get("minutes") ?? 0),
  });
  if (!saisie.success) return redirection("/regie?etat=erreur");

  await decalerDepuis(saisie.data.moment, saisie.data.minutes);
  return redirection("/regie?etat=decale");
}
