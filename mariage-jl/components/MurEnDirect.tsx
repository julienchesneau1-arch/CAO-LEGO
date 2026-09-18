"use client";

import { useEffect, useState } from "react";
import { Monogram } from "@/components/Monogram";

/**
 * Mur en direct pour projection (brief §8.7) : diaporama plein écran, fondu
 * de six secondes, monogramme en filigrane, QR générique dans un coin.
 *
 * Aucun compteur, aucun nom, aucun « j'aime » : un mur projeté dans une
 * salle ne doit rien apprendre sur qui a envoyé quoi (§17, §11).
 */
const DUREE_MS = 6000;

export function MurEnDirect({
  identifiants,
  qr,
  libelles,
}: {
  readonly identifiants: ReadonlyArray<string>;
  readonly qr: string;
  readonly libelles: {
    readonly titre: string;
    readonly attente: string;
    readonly signature: string;
  };
}) {
  const [index, setIndex] = useState(0);
  const [liste, setListe] = useState<ReadonlyArray<string>>(identifiants);

  // Le diaporama avance seul…
  useEffect(() => {
    if (liste.length === 0) return;
    const minuterie = setInterval(
      () => setIndex((precedent) => (precedent + 1) % liste.length),
      DUREE_MS,
    );
    return () => clearInterval(minuterie);
  }, [liste.length]);

  /**
   * …et la liste se renouvelle toutes les deux minutes, sans recharger la
   * page : un vidéoprojecteur reste branché des heures, et un rechargement
   * complet ferait clignoter l'écran devant tout le monde.
   */
  useEffect(() => {
    const rafraichir = async (): Promise<void> => {
      try {
        const reponse = await fetch("/live/liste", { cache: "no-store" });
        if (!reponse.ok) return;
        const donnees = (await reponse.json()) as { identifiants?: ReadonlyArray<string> };
        if (Array.isArray(donnees.identifiants)) setListe(donnees.identifiants);
      } catch {
        // Réseau coupé : on continue avec ce qu'on a déjà à l'écran.
      }
    };
    const minuterie = setInterval(() => void rafraichir(), 120_000);
    return () => clearInterval(minuterie);
  }, []);

  const courant = liste[index];

  return (
    <main
      className="relative flex h-dvh w-full items-center justify-center overflow-hidden"
      style={{ background: "var(--fond)" }}
    >
      {/* Filigrane : le monogramme, très discret, derrière les photos. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-5"
      >
        <Monogram hauteur={320} />
      </div>

      {courant === undefined ? (
        <p className="jl-titre px-8 text-center text-3xl">{libelles.attente}</p>
      ) : (
        liste.map((identifiant, position) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={identifiant}
            src={`/m/${identifiant}`}
            alt=""
            className="absolute inset-0 h-full w-full object-contain"
            style={{
              opacity: position === index ? 1 : 0,
              transition: "opacity 1.2s ease-in-out",
            }}
          />
        ))
      )}

      {/*
        Signature et adresse sur une seule rangée : deux coins absolus se
        chevauchaient dès qu'on projetait sur un écran étroit, ou qu'on
        ouvrait le mur depuis un téléphone pour vérifier.
      */}
      <div className="absolute inset-x-8 bottom-6 flex flex-wrap items-baseline justify-between gap-x-8 gap-y-1">
        <p className="jl-etiquette" style={{ color: "var(--doux)" }}>
          {libelles.signature}
        </p>
        {qr === "" ? null : (
          <p className="jl-etiquette" style={{ color: "var(--doux)" }}>
            {qr.replace(/^https:\/\//, "")}
          </p>
        )}
      </div>
    </main>
  );
}
