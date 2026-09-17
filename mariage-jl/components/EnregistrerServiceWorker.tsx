"use client";

import { useEffect } from "react";

/**
 * Enregistre le service worker après le chargement de la page, jamais avant :
 * il ne doit pas retarder le premier affichage (brief §12, « ouverture
 * signature jamais bloquante »).
 */
export function EnregistrerServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const enregistrer = () => {
      void navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        /* un service worker refusé ne doit jamais casser la page */
      });
    };
    if (document.readyState === "complete") enregistrer();
    else window.addEventListener("load", enregistrer, { once: true });
  }, []);

  return null;
}
