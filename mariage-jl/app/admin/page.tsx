import { Filet } from "@/components/Filet";
import { tableauDeBord } from "@/lib/invites";
import { nomMoment, moments } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";

const couleurMoment = (id: string): string | undefined =>
  MOMENTS.find((moment) => moment.id === id)?.hex;

/** Tableau de bord (brief §14) : ce qui compte, en un écran. */
export default async function PageAdmin() {
  const { langue, t } = await langueEtTextes();
  const [tableau, liste] = await Promise.all([tableauDeBord(), moments()]);

  const chiffres = [
    { libelle: t.admin.foyers, valeur: tableau.foyers },
    { libelle: t.admin.ouverts, valeur: tableau.ouverts },
    { libelle: t.admin.oui, valeur: tableau.oui },
    { libelle: t.admin.peutetre, valeur: tableau.peutetre },
    { libelle: t.admin.non, valeur: tableau.non },
    { libelle: t.admin.sans_reponse, valeur: tableau.sansReponse },
    { libelle: t.admin.personnes, valeur: tableau.invites },
    { libelle: t.admin.allergies, valeur: tableau.allergies },
  ];

  return (
    <main className="flex flex-col gap-10">
      <h1 className="jl-titre text-2xl">{t.admin.tableau}</h1>

      <dl className="grid grid-cols-2 gap-6">
        {chiffres.map((chiffre) => (
          <div key={chiffre.libelle} className="flex flex-col gap-1">
            <dd className="jl-titre text-3xl tabular-nums">{chiffre.valeur}</dd>
            <dt className="jl-doux text-sm">{chiffre.libelle}</dt>
          </div>
        ))}
      </dl>

      <section aria-labelledby="presences" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="presences" className="jl-etiquette">
          {t.admin.presences}
        </h2>
        <ul className="flex flex-col gap-3">
          {tableau.presencesParMoment.map((presence) => {
            const moment = liste.find((candidat) => candidat.id === presence.moment);
            return (
              <li key={presence.moment} className="flex flex-col gap-2">
                <div className="flex items-baseline justify-between gap-4">
                  <span>
                    {presence.moment} · {moment === undefined ? "" : nomMoment(moment, langue)}
                  </span>
                  <span className="tabular-nums">{presence.presents}</span>
                </div>
                <Filet
                  {...(couleurMoment(presence.moment) === undefined
                    ? {}
                    : { couleur: couleurMoment(presence.moment) as string })}
                  largeur={`${tableau.invites === 0 ? 0 : (presence.presents / tableau.invites) * 100}%`}
                />
              </li>
            );
          })}
        </ul>
      </section>

      {tableau.regimes.length === 0 ? null : (
        <section aria-labelledby="regimes" className="flex flex-col gap-3">
          <hr className="jl-filet" />
          <h2 id="regimes" className="jl-etiquette">
            {t.admin.regimes}
          </h2>
          <ul className="flex flex-col gap-2">
            {tableau.regimes.map((regime) => (
              <li key={regime.regime} className="flex justify-between gap-4">
                <span>{regime.regime}</span>
                <span className="tabular-nums">{regime.personnes}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
