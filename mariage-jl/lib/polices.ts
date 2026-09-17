import localFont from "next/font/local";

/**
 * Polices auto-hébergées (brief §3). Les fichiers vivent dans le dépôt : la
 * compilation ne dépend d'aucun réseau, et Next connaît les URL d'avance,
 * donc il les précharge — c'est ce qui ramène le LCP de l'accueil sous la
 * seconde. Les axes demandés par le brief (opsz 24, wght 470) sont appliqués
 * en CSS, sur `.jl-titre`.
 */
export const bodoni = localFont({
  src: [
    { path: "../assets/polices/bodoni-moda-latin.woff2", weight: "400 900", style: "normal" },
    {
      path: "../assets/polices/bodoni-moda-italique-latin.woff2",
      weight: "400 900",
      style: "italic",
    },
  ],
  display: "swap",
  preload: true,
  variable: "--police-titre",
  fallback: ["Times New Roman", "serif"],
});

export const cormorant = localFont({
  src: [
    { path: "../assets/polices/cormorant-garamond-latin.woff2", weight: "300 700", style: "normal" },
  ],
  display: "swap",
  preload: true,
  variable: "--police-texte",
  fallback: ["Georgia", "serif"],
});
