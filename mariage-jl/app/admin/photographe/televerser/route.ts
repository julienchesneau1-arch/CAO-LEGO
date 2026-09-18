import type { NextRequest } from "next/server";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { enregistrerMedia, octetsMax } from "@/lib/medias";

/**
 * Dépôt des photos du photographe. Les mêmes règles que pour un invité :
 * métadonnées retirées, format inconnu refusé, taille bornée. Seul le
 * consentement ne s'applique pas — ce sont les mariés qui déposent, et ils
 * ont déjà décidé.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  const session = await exigerAdmin();
  if (session === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const fichiers = donnees.getAll("fichiers").filter((valeur): valeur is File => valeur instanceof File);

  let ajoutees = 0;
  let refusees = 0;
  for (const fichier of fichiers) {
    if (fichier.size === 0 || fichier.size > octetsMax()) {
      refusees += 1;
      continue;
    }
    const resultat = await enregistrerMedia({
      // Les photos du photographe n'appartiennent à aucun foyer : elles sont
      // à tout le monde, et rien ne doit laisser croire le contraire.
      foyer: null,
      momentId: null,
      mime: fichier.type,
      octets: new Uint8Array(await fichier.arrayBuffer()),
      source: "photographe",
    });
    if ("refus" in resultat) refusees += 1;
    else ajoutees += 1;
  }

  return redirection(`/admin/photographe?ajoutees=${ajoutees}&refusees=${refusees}`);
}
