import { defaultCache } from "@serwist/next/worker";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { NetworkFirst, NetworkOnly, Serwist } from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope & WorkerGlobalScope;

/**
 * Service worker (brief §12 : programme, infos, FAQ et fiche de secours
 * consultables sans réseau une fois ouverts).
 *
 * Deux règles, dans cet ordre, et l'ordre est le fond du sujet :
 *
 * 1. **Seules les pages de contenu sont mises en cache.** Tout le reste du
 *    domaine — accueil, réponse, partage, espace des mariés, et jusqu'aux
 *    charges RSC que Next précharge derrière les liens — passe par le réseau
 *    et ne laisse aucune trace. Sans la troisième règle ci-dessous, le cache
 *    par défaut conservait la charge RSC de l'accueil, donc le nom du foyer
 *    et sa réponse, sur le disque du téléphone : un téléphone prêté ou perdu
 *    les rendait lisibles.
 * 2. **Aucune écriture n'est mise en cache** : une réponse part sur le
 *    réseau, ou elle attend dans la file (lib/file-attente.ts).
 */
const PAGES_DE_CONTENU = /^\/(programme|infos|faq)(\/|$)/;

const estStatique = (chemin: string): boolean =>
  chemin.startsWith("/_next/static/") ||
  chemin === "/sw.js" ||
  chemin === "/icon.svg" ||
  chemin === "/manifest.webmanifest";

const precache = self.__SW_MANIFEST ?? [];

const serwist = new Serwist({
  // L'écran hors ligne est précaché explicitement : les pages de cette
  // application sont dynamiques, le manifeste de compilation ne les contient
  // donc pas, et un écran de secours absent du cache ne sert à rien.
  precacheEntries: [...precache, { url: "/hors-ligne", revision: null }],
  skipWaiting: true,
  clientsClaim: true,
  runtimeCaching: [
    {
      matcher: ({ request }) => request.method !== "GET",
      handler: new NetworkOnly(),
    },
    {
      // Seules les **navigations** vers une page de contenu sont gardées.
      // Les charges RSC que Next précharge derrière les liens portent un
      // paramètre `_rsc` qui change à chaque chargement : les mettre en cache
      // faisait grossir le cache du téléphone indéfiniment, sans jamais
      // servir à afficher une page hors ligne.
      matcher: ({ request, sameOrigin, url }) =>
        sameOrigin &&
        PAGES_DE_CONTENU.test(url.pathname) &&
        !url.searchParams.has("_rsc") &&
        (request.mode === "navigate" || request.destination === "document"),
      handler: new NetworkFirst({
        cacheName: "jl-contenu",
        networkTimeoutSeconds: 4,
        plugins: [
          {
            cacheWillUpdate: async ({ response }) => (response.status === 200 ? response : null),
          },
        ],
      }),
    },
    {
      // Tout le reste du domaine qui n'est pas un fichier statique : jamais
      // en cache. Cette règle passe avant `defaultCache`, qui ne voit donc
      // plus que les fichiers statiques.
      matcher: ({ sameOrigin, url }) => sameOrigin && !estStatique(url.pathname),
      handler: new NetworkOnly(),
    },
    ...defaultCache,
  ],
  fallbacks: {
    entries: [
      {
        url: "/hors-ligne",
        matcher: ({ request }) => request.destination === "document",
      },
    ],
  },
});

serwist.addEventListeners();
