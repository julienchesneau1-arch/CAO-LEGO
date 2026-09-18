import type { NextRequest } from "next/server";
import { foyerCourant } from "@/lib/foyer";
import { etatJournee } from "@/lib/journee";
import { estDefiOuvert } from "@/lib/defis";
import { enregistrerMedia, octetsMax, type RefusEnvoi } from "@/lib/medias";

const MOMENTS = ["01", "02", "03", "04", "05"];

/**
 * Envoi d'un souvenir (brief §8.7). Répond en JSON, sans redirection : c'est
 * la file d'attente persistante du navigateur qui appelle cette route, et
 * elle a besoin d'un « oui » ou d'un « non » explicite pour savoir si elle
 * peut oublier l'envoi.
 *
 * Un refus porte une **raison** : l'écran la traduit. Un fichier que le
 * serveur ne sait pas nettoyer est refusé plutôt que stocké géolocalisé.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  const refus = (raison: RefusEnvoi, statut = 400): Response =>
    Response.json({ refus: raison }, { status: statut });

  const foyer = await foyerCourant();
  if (foyer === undefined) return refus("sans_foyer", 403);

  // La cérémonie débranchée et la coupure de la régie s'appliquent ici, pas
  // seulement à l'écran : un envoi rejoué plus tard doit être refusé aussi.
  const journee = await etatJournee();
  if (journee.envoisEnPause) return refus("envois_suspendus", 409);

  const donnees = await requete.formData();
  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File)) return refus("type_refuse");
  if (fichier.size > octetsMax()) return refus("trop_gros", 413);

  const momentBrut = donnees.get("moment")?.toString() ?? "";
  const moment = MOMENTS.includes(momentBrut) ? momentBrut : journee.courant?.id ?? null;

  /*
    Le défi vient du téléphone : on vérifie qu'il est publié et réellement
    écrit avant de l'attacher. Un identifiant bricolé n'accroche rien.
  */
  const defiBrut = donnees.get("defi")?.toString() ?? "";
  const defiId =
    defiBrut !== "" && (await estDefiOuvert(defiBrut)) ? defiBrut : null;

  const dureeBrute = Number(donnees.get("duree") ?? 0);
  const largeur = Number(donnees.get("largeur") ?? 0);
  const hauteur = Number(donnees.get("hauteur") ?? 0);

  const resultat = await enregistrerMedia({
    foyer: foyer.id,
    momentId: moment,
    mime: fichier.type,
    octets: new Uint8Array(await fichier.arrayBuffer()),
    defiId,
    ...(largeur > 0 ? { largeur } : {}),
    ...(hauteur > 0 ? { hauteur } : {}),
    ...(dureeBrute > 0 && dureeBrute <= 60 ? { dureeS: dureeBrute } : {}),
  });

  if ("refus" in resultat) return refus(resultat.refus);
  return Response.json({ id: resultat.id }, { status: 201 });
}
