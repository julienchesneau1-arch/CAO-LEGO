import Link from "next/link";
import { Filet } from "@/components/Filet";
import { langueEtTextes } from "@/lib/page-commune";
import { ambianceMoment, genreMoment, heure, moments, nomMoment } from "@/lib/moments";
import { formater } from "@/lib/i18n";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le programme — J & L" };

const couleur = (id: string): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/** Les cinq moments en cartes (brief §8.3). */
export default async function PageProgramme() {
  const { langue, t } = await langueEtTextes();
  const liste = await moments();

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.programme.titre}</h1>
        <p className="jl-doux">{t.programme.intro}</p>
      </header>

      <ol className="flex flex-col gap-10">
        {liste.map((moment) => {
          const debut = heure(moment.starts_at, langue);
          const fin = heure(moment.ends_at, langue);
          const horaire =
            debut === null
              ? t.programme.horaire_inconnu
              : fin === null
                ? formater(t.programme.a_partir_de, { debut })
                : formater(t.programme.de_a, { debut, fin });
          const ambiance = ambianceMoment(moment, langue);

          return (
            <li key={moment.id} className="flex flex-col gap-4">
              <Filet couleur={couleur(moment.id)} />
              <div className="flex flex-col gap-2">
                <p className="jl-numero">{moment.id}</p>
                <h2 className="jl-titre text-2xl">
                  {nomMoment(moment, langue)}
                  <span className="jl-doux text-base"> · {genreMoment(moment, langue)}</span>
                </h2>
                <p className={debut === null ? "jl-doux" : "tabular-nums"}>{horaire}</p>
                <p className="jl-doux">{moment.place ?? t.programme.lieu_inconnu}</p>
                {ambiance === null ? null : <p>{ambiance}</p>}
              </div>
              <Link
                href={`/programme/${moment.id}`}
                className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
              >
                {t.programme.detail_lien}
              </Link>
            </li>
          );
        })}
      </ol>

      <hr className="jl-filet" />

      <div className="flex flex-col gap-3">
        <a
          href="/programme/agenda.ics"
          className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
          download
        >
          {t.programme.agenda}
        </a>
        {liste.every((moment) => moment.starts_at === null) ? (
          <p className="jl-doux text-sm">{t.programme.agenda_journee}</p>
        ) : null}
      </div>
    </main>
  );
}
