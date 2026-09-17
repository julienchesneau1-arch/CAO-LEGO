import { cookies, headers } from "next/headers";
import { construireIcs, type EvenementIcs } from "@/lib/ics";
import { genreMoment, moments, nomMoment } from "@/lib/moments";
import { parametres } from "@/lib/foyer";
import { COOKIE_LANGUE, LANGUE_DEFAUT, estLangue } from "@/lib/i18n";

export const dynamic = "force-dynamic";

/**
 * « Ajouter à mon agenda » (brief §8.3). Tant que les horaires ne sont pas
 * connus, le fichier contient un seul événement : la journée du 3 juin 2028,
 * qui est une information certaine. Rien n'est inventé.
 */
export async function GET(): Promise<Response> {
  const entetes = await headers();
  const domaine = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "mariage-jl";
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeur) ? valeur : LANGUE_DEFAUT;

  const liste = await moments();
  const avecHoraires = liste.filter((moment) => moment.starts_at !== null);

  const evenements: EvenementIcs[] =
    avecHoraires.length > 0
      ? avecHoraires.map((moment) => ({
          uid: `moment-${moment.id}@${domaine}`,
          titre: `${nomMoment(moment, langue)} — ${genreMoment(moment, langue)}`,
          debut: moment.starts_at as Date,
          fin: moment.ends_at,
          ...(moment.place === null ? {} : { lieu: moment.place }),
        }))
      : [
          {
            uid: `mariage@${domaine}`,
            titre: "Julien & Lauriane",
            debut: (await parametres()).date_mariage,
            fin: null,
            journeeEntiere: true,
            lieu: "Domaine de Roiffé, 86120 Roiffé",
          },
        ];

  return new Response(construireIcs(evenements, { domaine }), {
    headers: {
      "content-type": "text/calendar; charset=utf-8",
      "content-disposition": 'attachment; filename="mariage-jl.ics"',
      "cache-control": "no-store",
    },
  });
}
