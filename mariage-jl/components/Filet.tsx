type Props = {
  /** Couleur du fil. Un fil coloré ne porte jamais de texte (brief §3). */
  readonly couleur?: string;
  readonly epaisseur?: number;
  readonly largeur?: string;
  readonly anime?: boolean;
};

export function Filet({ couleur, epaisseur = 2, largeur = "100%", anime = false }: Props) {
  return (
    <span
      aria-hidden="true"
      className={anime ? "jl-trace" : undefined}
      style={{
        display: "block",
        width: largeur,
        height: `${epaisseur}px`,
        background: couleur ?? "var(--filet)",
        transformOrigin: "left center",
      }}
    />
  );
}
