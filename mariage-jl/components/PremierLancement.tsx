"use client";

import { useEffect, useRef, useState } from "react";
import { ConfortLecture } from "./ConfortLecture";
import { Monogram } from "./Monogram";
import { PileCouleurs } from "./PileCouleurs";
import { MOMENTS } from "@/lib/tokens";
import type { Langue } from "@/lib/i18n";

const CLE = "jl_lancement";

type Libelles = {
  readonly passer: string;
  readonly suivant: string;
  readonly ecran1: string;
  readonly ecran3_titre: string;
  readonly ecran3_texte: string;
  readonly bienvenue: string;
  readonly confort: Parameters<typeof ConfortLecture>[0]["libelles"];
};

/**
 * Premier lancement en trois écrans, tous passables (brief §6).
 * 1. ouverture signature ; 2. confort de lecture ; 3. « Tout est ici. »
 * Vu une seule fois par appareil. Jamais bloquant : « Passer » est visible
 * immédiatement, et si le stockage local est indisponible, l'écran s'efface
 * quand même au premier geste.
 */
export function PremierLancement({
  libelles,
  langueCourante,
}: {
  readonly libelles: Libelles;
  readonly langueCourante: Langue;
}) {
  const [etat, setEtat] = useState<"inconnu" | "affiche" | "termine">("inconnu");
  const [ecran, setEcran] = useState(1);
  const dialogue = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let dejaVu = false;
    try {
      dejaVu = localStorage.getItem(CLE) === "1";
    } catch {
      /* mode privé : on montre l'ouverture, elle ne coûte rien */
    }
    setEtat(dejaVu ? "termine" : "affiche");
  }, []);

  // Tant que l'ouverture est là, la page ne défile pas derrière elle et le
  // focus y entre : sans cela, un lecteur d'écran lit l'accueil masqué.
  useEffect(() => {
    if (etat !== "affiche") return undefined;
    const precedent = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogue.current?.focus();
    return () => {
      document.body.style.overflow = precedent;
    };
  }, [etat]);

  const terminer = () => {
    try {
      localStorage.setItem(CLE, "1");
    } catch {
      /* rien à faire : l'écran se ferme de toute façon */
    }
    setEtat("termine");
  };

  if (etat !== "affiche") return null;

  return (
    <div
      ref={dialogue}
      role="dialog"
      aria-modal="true"
      aria-label={libelles.ecran1}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto px-6 py-10"
      style={{ background: "var(--fond)" }}
    >
      <button
        type="button"
        onClick={terminer}
        className="jl-cible jl-etiquette self-end"
      >
        {libelles.passer}
      </button>

      <div className="flex flex-1 flex-col justify-center gap-10">
        {ecran === 1 ? (
          <div className="flex flex-col items-center gap-8">
            <div className="flex w-full max-w-xs flex-col gap-2">
              {MOMENTS.map((moment, rang) => (
                <span
                  key={moment.id}
                  aria-hidden="true"
                  className="jl-ouverture-filet"
                  style={
                    {
                      display: "block",
                      height: "2px",
                      background: moment.hex,
                      ["--rang" as string]: String(rang),
                    } as React.CSSProperties
                  }
                />
              ))}
            </div>
            <div className="relative">
              <span className="jl-ouverture-contour block">
                <Monogram hauteur={104} variante="contour" titre={libelles.ecran1} />
              </span>
              <span className="jl-ouverture-plein absolute inset-0 block">
                <Monogram hauteur={104} variante="plein" />
              </span>
            </div>
          </div>
        ) : null}

        {ecran === 2 ? (
          <ConfortLecture libelles={libelles.confort} langueCourante={langueCourante} />
        ) : null}

        {ecran === 3 ? (
          <div className="flex flex-col gap-6">
            <PileCouleurs orientation="horizontale" />
            <p className="jl-titre text-3xl">{libelles.bienvenue}</p>
            <p className="jl-titre text-2xl">{libelles.ecran3_titre}</p>
            <p className="jl-doux max-w-prose">{libelles.ecran3_texte}</p>
          </div>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => (ecran === 3 ? terminer() : setEcran((n) => n + 1))}
        className="jl-cible mt-8 border px-5 py-3"
        style={{ borderColor: "var(--filet)" }}
      >
        {ecran === 3 ? libelles.ecran3_titre : libelles.suivant}
      </button>
    </div>
  );
}
