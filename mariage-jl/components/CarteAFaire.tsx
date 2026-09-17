import Link from "next/link";

/**
 * Une seule action à la fois (brief §8.1). Quand il n'y a plus rien à faire,
 * la carte le dit et ne propose rien : c'est le but.
 */
export function CarteAFaire({
  titre,
  action,
  lien,
}: {
  readonly titre: string;
  readonly action: string;
  readonly lien?: string;
}) {
  return (
    <section
      aria-labelledby="afaire-titre"
      className="flex flex-col gap-4 border p-6"
      style={{ borderColor: "var(--filet)" }}
    >
      <h2 id="afaire-titre" className="jl-etiquette">
        {titre}
      </h2>
      {lien === undefined ? (
        <p className="jl-titre text-2xl">{action}</p>
      ) : (
        <Link
          href={lien}
          className="jl-cible jl-titre flex items-center text-2xl underline decoration-1 underline-offset-8"
        >
          {action}
        </Link>
      )}
    </section>
  );
}
