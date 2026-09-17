"use client";

import { useEffect, useState } from "react";

type Libelles = {
  readonly titre: string;
  readonly explication: string;
  readonly activer: string;
  readonly active: string;
  readonly refuse: string;
  readonly impossible: string;
};

/**
 * Notifications (brief §17 : **ne jamais** demander l'autorisation au premier
 * chargement). Elle n'est demandée qu'au clic de l'invité, et le refus est
 * accepté sans insister ni redemander.
 */
export function Notifications({
  clePublique,
  libelles,
}: {
  readonly clePublique: string;
  readonly libelles: Libelles;
}) {
  const [etat, setEtat] = useState<"inconnu" | "possible" | "active" | "refuse" | "impossible">(
    "inconnu",
  );

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setEtat("impossible");
      return;
    }
    if (Notification.permission === "denied") {
      setEtat("refuse");
      return;
    }
    void navigator.serviceWorker.ready.then(async (enregistrement) => {
      const abonnement = await enregistrement.pushManager.getSubscription();
      setEtat(abonnement === null ? "possible" : "active");
    });
  }, []);

  const activer = async () => {
    try {
      const autorisation = await Notification.requestPermission();
      if (autorisation !== "granted") {
        setEtat("refuse");
        return;
      }
      const enregistrement = await navigator.serviceWorker.ready;
      const abonnement = await enregistrement.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: clePublique,
      });
      const reponse = await fetch("/push/abonner", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(abonnement.toJSON()),
      });
      setEtat(reponse.ok ? "active" : "impossible");
    } catch {
      setEtat("impossible");
    }
  };

  if (etat === "inconnu") return null;

  return (
    <section aria-labelledby="notifications" className="flex flex-col gap-3">
      <h2 id="notifications" className="jl-etiquette">
        {libelles.titre}
      </h2>
      <p className="jl-doux text-sm">{libelles.explication}</p>
      {etat === "possible" ? (
        <button
          type="button"
          onClick={() => void activer()}
          className="jl-cible self-start border px-5 py-3"
          style={{ borderColor: "var(--filet)" }}
        >
          {libelles.activer}
        </button>
      ) : (
        <p aria-live="polite" className="jl-doux">
          {etat === "active"
            ? libelles.active
            : etat === "refuse"
              ? libelles.refuse
              : libelles.impossible}
        </p>
      )}
    </section>
  );
}
