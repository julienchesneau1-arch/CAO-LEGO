/**
 * Source unique des jetons de la direction artistique (brief §2 et §3).
 * Les hex sont relevés sur une maquette écran : ils seront remplacés par les
 * références de l'imprimeur (question V0-08). Rien n'est dupliqué ailleurs.
 */

export const MOMENTS = [
  { id: "01", key: "eclat", ral: "RAL 1023", hex: "#E9B131" },
  { id: "02", key: "horizon", ral: "RAL 5015", hex: "#365D87" },
  { id: "03", key: "rencontre", ral: "RAL 2004", hex: "#CB5726" },
  { id: "04", key: "ivresse", ral: "RAL 3005", hex: "#721F23" },
  { id: "05", key: "nuit", ral: "RAL 4005", hex: "#84568D" },
] as const;

export type MomentKey = (typeof MOMENTS)[number]["key"];

export const NEUTRES = {
  noir: "#080808",
  ivoire: "#E9E2D8", // Le Fond — RAL 9010
  matiere: "#99836F", // La Matière — RAL 1019
  papierFond: "#E9E2D8",
  papierTexte: "#121212",
} as const;

/** Échelles de confort de lecture. Minimum absolu 16 px partout (brief §3). */
export const TAILLES_TEXTE = {
  normale: 18,
  grande: 21,
  "tres-grande": 25,
} as const;

export type TailleTexte = keyof typeof TAILLES_TEXTE;

export const MOUVEMENT = {
  ease: "cubic-bezier(0.22, 1, 0.36, 1)",
  court: 300,
  moyen: 600,
  long: 900,
  glissementMaxPx: 12,
} as const;

/* ---------- Contraste WCAG 2.2, calculé et non supposé ---------- */

function canalLineaire(v: number): number {
  const c = v / 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function luminance(hex: string): number {
  const m = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m || m[1] === undefined) throw new Error(`Hex invalide : ${hex}`);
  const n = Number.parseInt(m[1], 16);
  const r = canalLineaire((n >> 16) & 0xff);
  const g = canalLineaire((n >> 8) & 0xff);
  const b = canalLineaire(n & 0xff);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Rapport de contraste entre deux couleurs, de 1 à 21. */
export function contraste(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  const clair = Math.max(la, lb);
  const sombre = Math.min(la, lb);
  return (clair + 0.05) / (sombre + 0.05);
}

export const arrondi2 = (n: number): number => Math.round(n * 100) / 100;
