import { Filet } from "@/components/Filet";
import { formater } from "@/lib/i18n";
import { atteint, indicateurs, pourcentage } from "@/lib/indicateurs";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";

/**
 * Indicateurs de réussite (brief §16), **sans traceur**.
 *
 * Un indicateur non mesurable n'est pas caché : il figure dans la liste,
 * avec la raison. C'est plus utile qu'une case vide — et cela évite qu'un
 * chiffre approché finisse par être lu comme un fait.
 *
 * Aucun de ces chiffres n'est visible des invités : ce serait un compteur de
 * participation, ce que le brief §17 interdit.
 */
export default async function PageAdminIndicateurs() {
  const { t } = await langueEtTextes();
  const { liste, delaiMedianS } = await indicateurs();

  const objectif = (unite: string, valeur: number): string =>
    unite === "pourcentage"
      ? formater(t.indicateurs.objectif_pourcentage, { objectif: String(valeur) })
      : valeur === 0
        ? t.indicateurs.objectif_zero
        : formater(t.indicateurs.objectif_au_moins, { objectif: String(valeur) });

  const delai = (): string => {
    if (delaiMedianS === undefined) return t.indicateurs.delai_absent;
    if (delaiMedianS < 60) {
      return formater(t.indicateurs.delai_secondes, { secondes: String(delaiMedianS) });
    }
    return formater(t.indicateurs.delai_minutes, {
      minutes: String(Math.floor(delaiMedianS / 60)),
      secondes: String(delaiMedianS % 60),
    });
  };

  return (
    <main className="flex flex-col gap-8">
      <h1 className="jl-titre text-2xl">{t.indicateurs.titre}</h1>
      <p className="jl-doux">{t.indicateurs.intro}</p>

      <ul className="flex flex-col gap-8">
        {liste.map((indicateur) => {
          const part =
            indicateur.unite === "pourcentage" && indicateur.valeur !== undefined
              ? pourcentage(indicateur.valeur, indicateur.sur ?? 0)
              : undefined;
          const verdict = atteint(indicateur);

          return (
            <li key={indicateur.cle} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span>{t.indicateurs[indicateur.cle as "ouverts"]}</span>
                <span className="jl-titre text-2xl tabular-nums">
                  {indicateur.valeur === undefined
                    ? "—"
                    : indicateur.unite === "pourcentage"
                      ? part === undefined
                        ? "—"
                        : `${part}%`
                      : indicateur.valeur}
                </span>
              </div>

              {/* Le filet dit la proportion sans jamais devenir un classement. */}
              {part === undefined ? null : <Filet largeur={`${Math.min(100, part)}%`} />}

              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="jl-doux text-sm">
                  {objectif(indicateur.unite, indicateur.objectif)}
                  {indicateur.unite === "pourcentage" &&
                  indicateur.valeur !== undefined &&
                  indicateur.sur !== undefined &&
                  indicateur.sur > 0
                    ? ` · ${indicateur.valeur}/${indicateur.sur}`
                    : ""}
                </span>
                <span className="jl-etiquette">
                  {verdict === undefined
                    ? indicateur.valeur === undefined
                      ? t.indicateurs.indisponible
                      : t.indicateurs.base_vide
                    : verdict
                      ? t.indicateurs.atteint
                      : t.indicateurs.pas_encore}
                </span>
              </div>

              {indicateur.pourquoi === undefined ? null : (
                <p className="jl-doux text-sm">
                  {t.indicateurs[indicateur.pourquoi as "sans_traceur"]}
                </p>
              )}
            </li>
          );
        })}
      </ul>

      <section aria-labelledby="delai" className="flex flex-col gap-2">
        <hr className="jl-filet" />
        <h2 id="delai" className="jl-etiquette">
          {t.indicateurs.delai_titre}
        </h2>
        <p className="jl-titre text-xl tabular-nums">{delai()}</p>
      </section>
    </main>
  );
}
