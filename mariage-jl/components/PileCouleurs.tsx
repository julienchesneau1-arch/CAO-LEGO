import { MOMENTS } from "@/lib/tokens";

type Props = {
  /** Côté d'un carré en pixels (16 px dans la signature du faire-part). */
  readonly cote?: number;
  readonly espacement?: number;
  readonly orientation?: "verticale" | "horizontale";
};

/**
 * Pile des cinq couleurs (brief §3) : signature du faire-part.
 * Les couleurs sont des surfaces, jamais du texte.
 */
export function PileCouleurs({
  cote = 16,
  espacement = 4,
  orientation = "verticale",
}: Props) {
  return (
    <div
      aria-hidden="true"
      style={{
        display: "flex",
        flexDirection: orientation === "verticale" ? "column" : "row",
        gap: `${espacement}px`,
      }}
    >
      {MOMENTS.map((moment) => (
        <span
          key={moment.id}
          style={{ width: `${cote}px`, height: `${cote}px`, background: moment.hex }}
        />
      ))}
    </div>
  );
}
