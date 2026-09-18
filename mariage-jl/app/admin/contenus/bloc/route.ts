import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { enregistrerBloc, estCleBloc, lienAcceptable, texteOuNull } from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

const RETOUR = "/admin/contenus?section=infos";

const Saisie = z.object({
  cle: z.string().refine(estCleBloc),
  texte_fr: z.string().min(1).max(2000),
  texte_en: z.string().min(1).max(2000),
  lien: z.string().max(500).nullable(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  const session = await exigerAdmin();
  if (session === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    cle: donnees.get("cle"),
    texte_fr: donnees.get("texte_fr"),
    texte_en: donnees.get("texte_en"),
    lien: texteOuNull(donnees.get("lien")?.toString()),
  });
  if (!saisie.success) return redirection(`${RETOUR}&etat=erreur`);

  // Un lien invalide est signalé au lieu d'être enregistré : mieux vaut un
  // bloc sans lien qu'un lien qui casse la confiance des invités.
  if (saisie.data.lien !== null && !lienAcceptable(saisie.data.lien)) {
    return redirection(`${RETOUR}&etat=lien`);
  }

  const { cle, ...valeurs } = saisie.data;
  if (!estCleBloc(cle)) return redirection(`${RETOUR}&etat=erreur`);
  await enregistrerBloc(cle, valeurs, session.email);
  return redirection(`${RETOUR}&etat=enregistre`);
}
