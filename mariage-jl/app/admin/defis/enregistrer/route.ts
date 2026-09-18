import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { enregistrerDefi } from "@/lib/defis";
import { redirection } from "@/lib/http";

const Saisie = z.object({
  defi: z.string().uuid(),
  title_fr: z.string().min(1).max(120),
  title_en: z.string().min(1).max(120),
  published: z.boolean(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    defi: donnees.get("defi")?.toString(),
    title_fr: donnees.get("title_fr")?.toString().trim(),
    title_en: donnees.get("title_en")?.toString().trim(),
    published: donnees.get("published") === "1",
  });
  if (!saisie.success) return redirection("/admin/defis?etat=erreur");

  const { defi, ...valeurs } = saisie.data;
  await enregistrerDefi(defi, valeurs);
  return redirection("/admin/defis?etat=enregistre");
}
