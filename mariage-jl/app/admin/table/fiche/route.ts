import { headers } from "next/headers";
import { exigerAdmin } from "@/lib/admin";
import { contacts, contenus } from "@/lib/contenus";
import { numeroComposable } from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";
import { dictionnaire } from "@/lib/i18n";
import { ficheRegiePdf } from "@/lib/imprimables";
import { heure, moments, nomMoment } from "@/lib/moments";

/**
 * Fiche régie imprimable (brief §9) : horaires, contacts, procédures de
 * panne. Les procédures sont celles du §10, écrites une fois dans les
 * dictionnaires — donc traduisibles, et jamais recopiées à la main.
 */
export async function GET(): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const t = dictionnaire("fr");
  const entetes = await headers();
  const domaine = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "";
  const attente = t.commun.a_completer;

  const [listeMoments, listeContacts, blocs] = await Promise.all([
    moments(),
    contacts("fr"),
    contenus("fr"),
  ]);

  const wifi = blocs["jour.wifi"]?.texte ?? null;

  const pdf = await ficheRegiePdf(
    {
      domaine,
      moments: listeMoments.map((moment) => ({
        id: moment.id,
        nom: nomMoment(moment, "fr"),
        heure: heure(moment.starts_at, "fr"),
        lieu: moment.place,
      })),
      contacts: listeContacts
        .filter((contact) => contact.telephone !== null && !contact.nom.includes(attente))
        .map((contact) => ({
          role: contact.cle === "aide.regie" ? t.aide.regie : t.aide.temoin,
          nom: contact.nom,
          telephone: numeroComposable(contact.telephone as string),
        })),
      wifi: wifi === null || wifi.includes(attente) ? null : wifi,
      procedures: [
        { titre: t.imprimables.proc_reseau_titre, texte: t.imprimables.proc_reseau_texte },
        { titre: t.imprimables.proc_app_titre, texte: t.imprimables.proc_app_texte },
        { titre: t.imprimables.proc_retard_titre, texte: t.imprimables.proc_retard_texte },
        { titre: t.imprimables.proc_photo_titre, texte: t.imprimables.proc_photo_texte },
      ],
    },
    {
      titre: t.imprimables.fiche_titre,
      horaires: t.imprimables.horaires,
      contacts: t.imprimables.contacts,
      sans_contact: t.imprimables.sans_contact,
      procedures: t.imprimables.procedures,
      wifi: t.imprimables.wifi,
      heure_inconnue: t.imprimables.heure_inconnue,
    },
  );

  return new Response(new Uint8Array(pdf), {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": 'attachment; filename="fiche-regie-jl.pdf"',
      "cache-control": "no-store",
    },
  });
}
