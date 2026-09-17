import type { MetadataRoute } from "next";

/**
 * Manifeste de l'application (brief §5). Ajouter l'app à l'écran d'accueil
 * reste **facultatif** : le manifeste ne déclenche aucune invitation à
 * installer, il rend seulement l'icône et les couleurs correctes pour qui le
 * fait de lui-même.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Julien & Lauriane — 3 juin 2028",
    short_name: "J & L",
    description: "Le programme, l’accès et votre réponse, en un seul endroit.",
    start_url: "/",
    display: "standalone",
    background_color: "#080808",
    theme_color: "#080808",
    lang: "fr",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
