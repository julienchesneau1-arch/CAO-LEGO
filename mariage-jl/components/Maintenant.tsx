import Link from "next/link";
import { CompteDiscret } from "@/components/CompteDiscret";
import { Filet } from "@/components/Filet";
import { itineraires } from "@/lib/cartes";
import type { EtatJournee } from "@/lib/journee";
import { formater, type Langue } from "@/lib/i18n";
import { genreMoment, heure, nomMoment } from "@/lib/moments";
import { LIVREES } from "@/lib/navigation";
import { MOMENTS } from "@/lib/tokens";

const couleur = (id: string): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

type Libelles = {
  readonly maintenant: Record<string, string>;
  readonly adresse: string;
};

/**
 * « Maintenant » (brief §8.6). En grand le moment en cours, en dessous le
 * suivant avec un compte à rebours discret, puis quatre raccourcis. Les
 * raccourcis qui mènent à un écran pas encore livré ne sont **pas** affichés :
 * mieux vaut trois liens qui marchent que quatre dont un est mort.
 */
export function Maintenant({
  etat,
  langue,
  libelles,
}: {
  readonly etat: EtatJournee;
  readonly langue: Langue;
  readonly libelles: Libelles;
}) {
  const t = libelles.maintenant;
  const raccourcis = [
    { cle: "ma_table", chemin: "/ma-table" },
    { cle: "souvenir", chemin: "/photos/envoyer" },
    { cle: "aide", chemin: "/aide" },
  ].filter((raccourci) => LIVREES.has(raccourci.chemin));

  const finCourant = heure(etat.courant?.ends_at ?? null, langue);

  return (
    <div className="flex flex-col gap-10">
      {/* La cérémonie débranchée passe avant tout le reste : c'est le seul
          moment où l'écran demande qu'on le range. */}
      {etat.pendantCeremonie ? (
        <section
          aria-labelledby="debranchee"
          className="flex flex-col gap-3 border p-6"
          style={{ borderColor: couleur("02") }}
        >
          <h2 id="debranchee" className="jl-titre text-2xl">
            {t["debranchee_titre"]}
          </h2>
          <p>{t["debranchee_texte"]}</p>
        </section>
      ) : null}

      {!etat.horairesConnus ? (
        <p className="jl-doux">{t["horaires_inconnus"]}</p>
      ) : (
        <>
          <section aria-labelledby="en-cours" className="flex flex-col gap-4">
            <h2 id="en-cours" className="jl-etiquette">
              {t["en_cours"]}
            </h2>
            {etat.courant === undefined ? (
              <p className="jl-doux">{t["entre_deux"]}</p>
            ) : (
              <>
                <Filet couleur={couleur(etat.courant.id)} />
                <p className="jl-numero">{etat.courant.id}</p>
                <p className="jl-titre text-4xl">{nomMoment(etat.courant, langue)}</p>
                <p className="jl-doux">
                  {genreMoment(etat.courant, langue)} ·{" "}
                  {finCourant === null
                    ? t["sans_fin"]
                    : formater(t["jusqua"] ?? "", { heure: finCourant })}
                </p>
                {etat.courant.place === null ? null : <p>{etat.courant.place}</p>}
              </>
            )}
          </section>

          {etat.suivant === undefined ? null : (
            <section aria-labelledby="ensuite" className="flex flex-col gap-3">
              <hr className="jl-filet" />
              <h2 id="ensuite" className="jl-etiquette">
                {t["ensuite"]}
              </h2>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <p className="jl-titre text-2xl">{nomMoment(etat.suivant, langue)}</p>
                {etat.suivant.starts_at === null ? null : (
                  <CompteDiscret
                    cibleIso={etat.suivant.starts_at.toISOString()}
                    initialMinutes={Math.max(
                      0,
                      Math.floor((etat.suivant.starts_at.getTime() - Date.now()) / 60_000),
                    )}
                    libelles={{
                      dans_minutes: t["dans_minutes"] ?? "",
                      dans_longtemps: t["dans_longtemps"] ?? "",
                      commence: t["commence"] ?? "",
                    }}
                  />
                )}
              </div>
            </section>
          )}
        </>
      )}

      {etat.envoisEnPause && !etat.pendantCeremonie ? (
        <p className="jl-doux">{t["envois_coupes"]}</p>
      ) : null}

      <section aria-labelledby="raccourcis" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="raccourcis" className="jl-etiquette">
          {t["raccourcis"]}
        </h2>
        <ul className="flex flex-wrap gap-3">
          {raccourcis.map((raccourci) => (
            <li key={raccourci.cle}>
              <Link
                href={raccourci.chemin}
                className="jl-cible flex items-center border px-4 py-3"
                style={{ borderColor: "var(--filet)" }}
              >
                {t[raccourci.cle]}
              </Link>
            </li>
          ))}
          <li>
            <a
              href={itineraires(libelles.adresse)[0]?.url ?? "#"}
              rel="noreferrer"
              target="_blank"
              className="jl-cible flex items-center border px-4 py-3"
              style={{ borderColor: "var(--filet)" }}
            >
              {t["itineraire"]}
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
