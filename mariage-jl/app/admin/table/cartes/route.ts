import { headers } from "next/headers";
import { exigerAdmin } from "@/lib/admin";
import { contacts, contenus } from "@/lib/contenus";
import { redirection } from "@/lib/http";
import { dictionnaire } from "@/lib/i18n";
import { cartesDeTablePdf, type CarteDeTable } from "@/lib/imprimables";
import { heure, moments, nomMoment } from "@/lib/moments";
import { numeroComposable } from "@/lib/contenus-admin";
import { prenomsDeLaTable, tables } from "@/lib/table";

/**
 * Cartes de table imprimables (brief §10, plan B). Une carte par table, avec
 * le QR générique, les cinq moments, le Wi-Fi et un numéro : si l'application
 * ou le réseau tombe, personne n'est perdu.
 */
export async function GET(): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const t = dictionnaire("fr");
  const entetes = await headers();
  const domaine = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "";

  const [liste, listeMoments, blocs, listeContacts] = await Promise.all([
    tables(),
    moments(),
    contenus("fr"),
    contacts("fr"),
  ]);

  const cartes: CarteDeTable[] = [];
  for (const table of liste) {
    cartes.push({ table: table.label, prenoms: await prenomsDeLaTable(table.id) });
  }

  const regie = listeContacts.find((contact) => contact.cle === "aide.regie");
  const wifi = blocs["jour.wifi"]?.texte ?? null;
  const attente = t.commun.a_completer;

  const pdf = await cartesDeTablePdf(cartes, {
    domaine,
    moments: listeMoments.map((moment) => ({
      id: moment.id,
      nom: nomMoment(moment, "fr"),
      heure: heure(moment.starts_at, "fr"),
      lieu: moment.place,
    })),
    // Un « [À COMPLÉTER] » imprimé serait pire que rien : on n'imprime que
    // ce qui est réellement écrit.
    wifi: wifi === null || wifi.includes(attente) ? null : wifi,
    contact:
      regie?.telephone == null || regie.nom.includes(attente)
        ? null
        : {
            role: t.aide.regie,
            nom: regie.nom,
            telephone: numeroComposable(regie.telephone),
          },
    libelles: {
      signature: t.accueil.signature,
      programme: t.imprimables.programme,
      heure_inconnue: t.imprimables.heure_inconnue,
      wifi: t.imprimables.wifi,
    },
  });

  return new Response(new Uint8Array(pdf), {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": 'attachment; filename="cartes-de-table-jl.pdf"',
      "cache-control": "no-store",
    },
  });
}
