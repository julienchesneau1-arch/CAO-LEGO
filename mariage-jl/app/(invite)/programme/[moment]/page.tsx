import Link from "next/link";
import { notFound } from "next/navigation";
import { Filet } from "@/components/Filet";
import { detailMoment, genreMoment, heure, moments, nomMoment } from "@/lib/moments";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";

/** « Le déroulé en détail » : pour ceux que l'inconnu inquiète (brief §8.3). */
export default async function PageMoment({
  params,
}: {
  readonly params: Promise<{ moment: string }>;
}) {
  const { moment: identifiant } = await params;
  const { langue, t } = await langueEtTextes();
  const moment = (await moments()).find((candidat) => candidat.id === identifiant);
  if (moment === undefined) notFound();

  const debut = heure(moment.starts_at, langue);
  const fin = heure(moment.ends_at, langue);
  const detail = detailMoment(moment, langue);
  const couleur = MOMENTS.find((m) => m.id === moment.id)?.hex ?? "var(--filet)";

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <Filet couleur={couleur} />
      <header className="flex flex-col gap-2">
        <p className="jl-numero">{moment.id}</p>
        <h1 className="jl-titre text-3xl">{nomMoment(moment, langue)}</h1>
        <p className="jl-doux">{genreMoment(moment, langue)}</p>
        <p className={debut === null ? "jl-doux" : "tabular-nums"}>
          {debut === null
            ? t.programme.horaire_inconnu
            : fin === null
              ? formater(t.programme.a_partir_de, { debut })
              : formater(t.programme.de_a, { debut, fin })}
        </p>
        <p className="jl-doux">{moment.place ?? t.programme.lieu_inconnu}</p>
      </header>

      <section aria-labelledby="deroule" className="flex flex-col gap-3">
        <h2 id="deroule" className="jl-etiquette">
          {t.programme.detail_titre}
        </h2>
        <p className={detail === null ? "jl-doux" : undefined}>
          {detail ?? t.programme.detail_absent}
        </p>
      </section>

      <Link
        href="/programme"
        className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
      >
        {t.programme.retour}
      </Link>
    </main>
  );
}
