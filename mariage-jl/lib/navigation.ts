import type { Periode } from "./periode";

/**
 * Une seule barre de navigation, cinq onglets au maximum, dont le contenu
 * change avec la période (brief §7).
 *
 * `LIVREES` est la liste des écrans réellement en ligne : la navigation
 * n'affiche jamais un onglet qui mènerait à une page absente. C'est ce qui
 * permet de livrer version par version sans jamais montrer un cul-de-sac.
 */
export const LIVREES = new Set(["/", "/programme", "/reponse", "/infos", "/faq"]);

export type Onglet = { readonly cle: string; readonly chemin: string };

const ONGLETS: Readonly<Record<Periode, ReadonlyArray<Onglet>>> = {
  avant: [
    { cle: "accueil", chemin: "/" },
    { cle: "programme", chemin: "/programme" },
    { cle: "reponse", chemin: "/reponse" },
    { cle: "infos", chemin: "/infos" },
    { cle: "faq", chemin: "/faq" },
  ],
  semaine: [
    { cle: "accueil", chemin: "/" },
    { cle: "programme", chemin: "/programme" },
    { cle: "infos", chemin: "/infos" },
    { cle: "table", chemin: "/ma-table" },
    { cle: "faq", chemin: "/faq" },
  ],
  jour: [
    { cle: "maintenant", chemin: "/" },
    { cle: "programme", chemin: "/programme" },
    { cle: "photos", chemin: "/photos" },
    { cle: "table", chemin: "/ma-table" },
    { cle: "aide", chemin: "/aide" },
  ],
  apres: [
    { cle: "merci", chemin: "/" },
    { cle: "photos", chemin: "/photos" },
    { cle: "film", chemin: "/film" },
    { cle: "messages", chemin: "/messages" },
    { cle: "donnees", chemin: "/mes-donnees" },
  ],
};

export function onglets(periode: Periode): ReadonlyArray<Onglet> {
  return ONGLETS[periode].filter((onglet) => LIVREES.has(onglet.chemin));
}
