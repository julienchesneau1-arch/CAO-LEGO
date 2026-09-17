import { MOMENTS } from "@/lib/tokens";

type Etape = { readonly libelle: string; readonly franchie: boolean };

/**
 * Cinq filets qui se remplissent au fil des étapes (brief §8.1).
 * La couleur ne porte jamais l'information seule : chaque filet est étiqueté,
 * et l'état est annoncé aux lecteurs d'écran.
 */
export function FiletsEtapes({ etapes }: { readonly etapes: ReadonlyArray<Etape> }) {
  return (
    <ol className="flex flex-col gap-3">
      {etapes.map((etape, index) => {
        const couleur = MOMENTS[index]?.hex;
        return (
          <li key={etape.libelle} className="flex items-center gap-4">
            <span
              aria-hidden="true"
              style={{
                display: "block",
                width: "3.5rem",
                height: "2px",
                background: etape.franchie ? couleur : "var(--filet)",
              }}
            />
            <span className={etape.franchie ? undefined : "jl-doux"}>
              {etape.libelle}
              {etape.franchie ? <span className="sr-only"> — fait</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
