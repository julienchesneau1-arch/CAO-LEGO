import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import {
  enregistrerContact,
  estCleContact,
  telephoneAcceptable,
  texteOuNull,
} from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

const RETOUR = "/admin/contenus?section=contacts";

const Saisie = z.object({
  cle: z.string().refine(estCleContact),
  texte_fr: z.string().min(1).max(120),
  texte_en: z.string().min(1).max(120),
  telephone: z.string().max(40).nullable(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  const session = await exigerAdmin();
  if (session === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({
    cle: donnees.get("cle"),
    texte_fr: donnees.get("texte_fr"),
    texte_en: donnees.get("texte_en"),
    telephone: texteOuNull(donnees.get("telephone")?.toString()),
  });
  if (!saisie.success) return redirection(`${RETOUR}&etat=erreur`);

  // Un numéro qui ne se compose pas produirait un bouton d'appel mort le
  // jour où quelqu'un en a vraiment besoin.
  if (saisie.data.telephone !== null && !telephoneAcceptable(saisie.data.telephone)) {
    return redirection(`${RETOUR}&etat=telephone`);
  }

  const { cle, ...valeurs } = saisie.data;
  if (!estCleContact(cle)) return redirection(`${RETOUR}&etat=erreur`);
  await enregistrerContact(cle, valeurs, session.email);
  return redirection(`${RETOUR}&etat=enregistre`);
}
