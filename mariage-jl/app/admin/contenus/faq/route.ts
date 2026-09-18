import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { ajouterFaq, enregistrerFaq, supprimerFaq } from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

const RETOUR = "/admin/contenus?section=faq";

const Saisie = z.object({
  question_fr: z.string().min(2).max(300),
  question_en: z.string().min(2).max(300),
  answer_fr: z.string().min(1).max(2000),
  answer_en: z.string().min(1).max(2000),
  published: z.boolean(),
  sort_order: z.number().int().min(0).max(999),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const id = donnees.get("id")?.toString() ?? "";

  if (donnees.get("supprimer") === "1") {
    if (id === "") return redirection(`${RETOUR}&etat=erreur`);
    await supprimerFaq(id);
    return redirection(`${RETOUR}&etat=supprime`);
  }

  const saisie = Saisie.safeParse({
    question_fr: donnees.get("question_fr"),
    question_en: donnees.get("question_en"),
    answer_fr: donnees.get("answer_fr"),
    answer_en: donnees.get("answer_en"),
    published: donnees.get("published") === "1",
    sort_order: Number(donnees.get("sort_order") ?? 0),
  });
  if (!saisie.success) return redirection(`${RETOUR}&etat=erreur`);

  if (donnees.get("action") === "ajout") await ajouterFaq(saisie.data);
  else if (id !== "") await enregistrerFaq(id, saisie.data);
  else return redirection(`${RETOUR}&etat=erreur`);

  return redirection(`${RETOUR}&etat=enregistre`);
}
