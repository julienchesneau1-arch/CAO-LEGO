/** Comparaison souple d'un nom saisi à la main : casse et accents ignorés. */
export function normaliser(valeur: string): string {
  return valeur
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function contientNom(candidats: ReadonlyArray<string>, saisi: string): boolean {
  const cible = normaliser(saisi);
  if (cible.length < 2) return false;
  return candidats.some((candidat) => {
    const normalise = normaliser(candidat);
    return normalise.includes(cible) || cible.includes(normalise);
  });
}
