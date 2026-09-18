import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { enregistrerDateLimite } from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

/** Date limite de réponse. Vide est une valeur valable : rien n'est décidé. */
const Saisie = z.object({
  date_limite: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .nullable(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const brute = String(donnees.get("date_limite") ?? "").trim();
  const saisie = Saisie.safeParse({ date_limite: brute === "" ? null : brute });
  if (!saisie.success) return redirection("/admin/contenus?section=journee&etat=erreur");

  await enregistrerDateLimite(saisie.data.date_limite);
  return redirection("/admin/contenus?section=journee&etat=enregistre");
}
