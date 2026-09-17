import { MONOGRAMME_TRACES, MONOGRAMME_VIEWBOX } from "./monogram.generated";

type Variante = "plein" | "contour";

type Props = {
  /** Hauteur du monogramme en pixels. La largeur suit le tracé. */
  readonly hauteur?: number;
  readonly variante?: Variante;
  /** Titre lu par les lecteurs d'écran ; absent = purement décoratif. */
  readonly titre?: string;
  readonly className?: string;
};

const [, , LARGEUR_VB, HAUTEUR_VB] = MONOGRAMME_VIEWBOX.split(" ").map(Number);
const RAPPORT = (LARGEUR_VB ?? 1) / (HAUTEUR_VB ?? 1);

/**
 * Monogramme en tracés SVG (brief §3) : aucune dépendance au rendu des
 * polices, donc identique à l'écran, en PDF et sur la page de secours.
 */
export function Monogram({
  hauteur = 64,
  variante = "plein",
  titre,
  className,
}: Props) {
  const largeur = Math.round(hauteur * RAPPORT);
  const contour = variante === "contour";
  return (
    <svg
      viewBox={MONOGRAMME_VIEWBOX}
      width={largeur}
      height={hauteur}
      className={className}
      role={titre ? "img" : "presentation"}
      aria-label={titre}
      aria-hidden={titre ? undefined : true}
      focusable="false"
    >
      <g
        fill={contour ? "none" : "currentColor"}
        stroke={contour ? "currentColor" : "none"}
        strokeWidth={contour ? (HAUTEUR_VB ?? 1) / hauteur : undefined}
        vectorEffect={contour ? "non-scaling-stroke" : undefined}
      >
        {MONOGRAMME_TRACES.map((trace) => (
          <path key={trace.lettre} d={trace.d} />
        ))}
      </g>
    </svg>
  );
}
