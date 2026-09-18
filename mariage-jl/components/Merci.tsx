import Link from "next/link";
import { Filet } from "@/components/Filet";
import type { Echeance } from "@/lib/apres";
import { formater, formaterDate, type Langue } from "@/lib/i18n";
import { LIVREES } from "@/lib/navigation";

/**
 * « Merci » (brief §8.11), l'écran de la période « Après ».
 *
 * Il dit trois choses, dans cet ordre : merci, voilà ce qu'il reste à voir,
 * et voilà jusqu'à quand. Les dates de fin ne sont pas une mention légale
 * en bas de page : un invité a le droit de savoir quand ses photos
 * disparaîtront, et de les emporter avant.
 */
export function Merci({
  message,
  vignettes,
  echeances,
  langue,
  libelles,
  reconnu,
}: {
  readonly message: string | null;
  readonly vignettes: ReadonlyArray<string>;
  readonly echeances: ReadonlyArray<Echeance>;
  readonly langue: Langue;
  readonly libelles: Record<string, string>;
  readonly reconnu: boolean;
}) {
  const t = libelles;
  const le = (quoi: string): string | undefined => {
    const trouve = echeances.find((echeance) => echeance.quoi === quoi);
    return trouve === undefined ? undefined : formaterDate(trouve.le, langue);
  };

  const liens = [
    { cle: "photographe", chemin: "/photographe" },
    { cle: "film", chemin: "/film" },
    { cle: "messages", chemin: "/messages" },
    { cle: "donnees", chemin: "/mes-donnees" },
  ].filter((lien) => LIVREES.has(lien.chemin));

  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="merci" className="flex flex-col gap-4">
        <Filet />
        <h2 id="merci" className="jl-titre text-3xl">
          {t["titre"]}
        </h2>
        <p>{t["intro"]}</p>
        {/* Le mot des mariés : tant qu'il n'est pas écrit, l'écran le dit. */}
        <p className={message === null ? "jl-doux" : ""}>{message ?? t["attente"]}</p>
      </section>

      {vignettes.length === 0 ? null : (
        <section aria-labelledby="souvenirs" className="flex flex-col gap-4">
          <hr className="jl-filet" />
          <h2 id="souvenirs" className="jl-etiquette">
            {t["souvenirs"]}
          </h2>
          <ul className="grid grid-cols-3 gap-2">
            {vignettes.map((identifiant) => (
              <li key={identifiant}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/m/${identifiant}`}
                  alt=""
                  loading="lazy"
                  className="aspect-square w-full object-cover"
                />
              </li>
            ))}
          </ul>
          <Link
            href="/photos"
            className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
          >
            {t["voir_tout"]}
          </Link>
        </section>
      )}

      {liens.length === 0 ? null : (
        <nav aria-label={t["titre"]} className="flex flex-col gap-3">
          <hr className="jl-filet" />
          {liens.map((lien) => (
            <Link
              key={lien.cle}
              href={lien.chemin}
              className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
            >
              {t[lien.cle]}
            </Link>
          ))}
        </nav>
      )}

      {!reconnu ? null : (
        <section aria-labelledby="archives" className="flex flex-col gap-4">
          <hr className="jl-filet" />
          <h2 id="archives" className="jl-etiquette">
            {t["archives"]}
          </h2>
          <p className="jl-doux text-sm">{t["archive_aide"]}</p>
          <div className="flex flex-wrap gap-4">
            <a
              href="/photos/archive"
              className="jl-cible flex items-center border px-5 py-3"
              style={{ borderColor: "var(--filet)" }}
            >
              {t["archive_toutes"]}
            </a>
            <a
              href="/photos/archive?mes=1"
              className="jl-cible flex items-center border px-5 py-3"
              style={{ borderColor: "var(--filet)" }}
            >
              {t["archive_mes"]}
            </a>
          </div>
        </section>
      )}

      <section aria-labelledby="jusqua" className="flex flex-col gap-3">
        <hr className="jl-filet" />
        <h2 id="jusqua" className="jl-etiquette">
          {t["fin_titre"]}
        </h2>
        <ul className="jl-doux flex flex-col gap-2">
          {le("acces") === undefined ? null : (
            <li>{formater(t["fin_acces"] ?? "", { date: le("acces") as string })}</li>
          )}
          {le("medias") === undefined ? null : (
            <li>{formater(t["fin_medias"] ?? "", { date: le("medias") as string })}</li>
          )}
          {le("reponses") === undefined ? null : (
            <li>{formater(t["fin_reponses"] ?? "", { date: le("reponses") as string })}</li>
          )}
          {le("allergies") === undefined ? null : (
            <li>{formater(t["fin_allergies"] ?? "", { date: le("allergies") as string })}</li>
          )}
        </ul>
      </section>
    </div>
  );
}
