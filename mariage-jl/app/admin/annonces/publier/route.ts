import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { publierAnnonce } from "@/lib/annonces";
import { redirection } from "@/lib/http";
import { notifier, pushConfigure } from "@/lib/push";

/**
 * Publication d'une annonce (brief V2). La notification est **optionnelle** :
 * une annonce peut être publiée sans réveiller les téléphones, ce qui est le
 * cas le plus fréquent avant le jour J.
 */
const Saisie = z.object({
  texte_fr: z.string().min(2).max(500),
  texte_en: z.string().min(2).max(500),
  notifier: z.boolean(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    texte_fr: donnees.get("texte_fr"),
    texte_en: donnees.get("texte_en"),
    notifier: donnees.get("notifier") === "1",
  });
  if (!saisie.success) return redirection("/admin/annonces?etat=erreur");

  await publierAnnonce(saisie.data.texte_fr, saisie.data.texte_en, "admin");

  if (saisie.data.notifier && pushConfigure()) {
    const envoi = await notifier("Julien & Lauriane", saisie.data.texte_fr, "/annonces");
    return redirection(`/admin/annonces?etat=publiee&envoyees=${envoi.envoyes}`);
  }
  return redirection("/admin/annonces?etat=publiee");
}
