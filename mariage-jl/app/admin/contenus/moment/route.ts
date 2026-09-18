import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { enregistrerMoment, heureAcceptable, texteOuNull } from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

const RETOUR = "/admin/contenus?section=moments";

/**
 * Horaires et textes d'un moment. Les cinq identifiants sont fermés : rien
 * d'autre ne peut être créé depuis ici, la direction artistique du brief §5
 * ne se négocie pas depuis un formulaire.
 */
const Saisie = z.object({
  id: z.enum(["01", "02", "03", "04", "05"]),
  debut: z.string().refine(heureAcceptable).nullable(),
  fin: z.string().refine(heureAcceptable).nullable(),
  place: z.string().max(200).nullable(),
  ambience_fr: z.string().max(200).nullable(),
  ambience_en: z.string().max(200).nullable(),
  detail_fr: z.string().max(1000).nullable(),
  detail_en: z.string().max(1000).nullable(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const champ = (nom: string): string | null => texteOuNull(donnees.get(nom)?.toString());
  const saisie = Saisie.safeParse({
    id: donnees.get("id"),
    debut: champ("debut"),
    fin: champ("fin"),
    place: champ("place"),
    ambience_fr: champ("ambience_fr"),
    ambience_en: champ("ambience_en"),
    detail_fr: champ("detail_fr"),
    detail_en: champ("detail_en"),
  });
  if (!saisie.success) return redirection(`${RETOUR}&etat=erreur`);

  const { id, ...reste } = saisie.data;
  await enregistrerMoment(id, reste);
  return redirection(`${RETOUR}&etat=enregistre`);
}
