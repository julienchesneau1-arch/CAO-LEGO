"use client";

import { useCallback, useEffect, useState } from "react";
import { enAttente, mettreEnAttente, vider } from "@/lib/file-attente";

type Libelles = {
  readonly enAttente: string;
  readonly enAttentePluriel: string;
  readonly envoye: string;
};

const INTERVALLE_REESSAI_MS = 20_000;

/**
 * Filet de sécurité des formulaires qui doivent survivre à une coupure
 * (brief §12, et §3 : « Tout ce que vous faites sera envoyé dès son retour »).
 *
 * Sans JavaScript, le formulaire part normalement : cette couche n'enlève
 * rien, elle ajoute. Avec JavaScript, l'envoi passe par `fetch` pour que
 * l'échec soit rattrapable — se fier au seul indicateur « hors ligne » du
 * navigateur ne suffit pas : au domaine, le téléphone se croit connecté alors
 * que plus rien ne passe.
 *
 * Limite honnête : sur iPhone, rien ne repart tant que l'application est
 * fermée (Safari n'a pas la synchronisation en arrière-plan). La reprise a
 * lieu à la réouverture, et l'écran l'annonce au lieu de promettre l'inverse.
 */
export function FileAttente({ libelles }: { readonly libelles: Libelles }) {
  const [attente, setAttente] = useState(0);
  const [vientDePartir, setVientDePartir] = useState(false);

  const rafraichir = useCallback(async () => {
    try {
      setAttente((await enAttente()).length);
      return true;
    } catch {
      return false; // IndexedDB refusé (navigation privée) : on n'insiste pas
    }
  }, []);

  const tenterEnvoi = useCallback(async () => {
    try {
      if ((await vider()) > 0) setVientDePartir(true);
    } catch {
      /* la file reste en place, on réessaiera */
    }
    await rafraichir();
  }, [rafraichir]);

  useEffect(() => {
    void tenterEnvoi();

    const surEnvoi = (evenement: Event) => {
      const cible = evenement.target;
      if (!(cible instanceof HTMLFormElement) || !cible.hasAttribute("data-file-attente")) return;

      evenement.preventDefault();
      const donnees = new FormData(cible);
      const soumetteur = (evenement as SubmitEvent).submitter;
      if (soumetteur instanceof HTMLButtonElement && soumetteur.name !== "") {
        donnees.append(soumetteur.name, soumetteur.value);
      }

      void (async () => {
        try {
          const reponse = await fetch(cible.action, { method: "POST", body: donnees });
          if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
          location.assign(reponse.url);
          return;
        } catch {
          // Réseau absent ou serveur injoignable : on garde tout.
          const champs = [...donnees.entries()]
            .filter((entree): entree is [string, string] => typeof entree[1] === "string")
            .map(([cle, valeur]) => [cle, valeur] as const);
          await mettreEnAttente({ action: cible.action, champs, cree: Date.now() });
          await rafraichir();
        }
      })();
    };

    const surRetour = () => void tenterEnvoi();

    document.addEventListener("submit", surEnvoi, true);
    window.addEventListener("online", surRetour);
    document.addEventListener("visibilitychange", surRetour);
    // Le retour du réseau ne déclenche pas toujours d'événement — un serveur
    // qui revient, par exemple. On réessaie donc tranquillement.
    const minuterie = setInterval(surRetour, INTERVALLE_REESSAI_MS);

    return () => {
      document.removeEventListener("submit", surEnvoi, true);
      window.removeEventListener("online", surRetour);
      document.removeEventListener("visibilitychange", surRetour);
      clearInterval(minuterie);
    };
  }, [rafraichir, tenterEnvoi]);

  if (attente === 0 && !vientDePartir) return null;

  return (
    <p
      aria-live="polite"
      data-file-attente-indicateur=""
      className="jl-doux border p-4 text-sm"
      style={{ borderColor: "var(--filet)" }}
    >
      {attente === 0
        ? libelles.envoye
        : (attente === 1 ? libelles.enAttente : libelles.enAttentePluriel).replace(
            "{nombre}",
            String(attente),
          )}
    </p>
  );
}
