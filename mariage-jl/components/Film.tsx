"use client";

import { useState } from "react";
import { Monogram } from "./Monogram";

/**
 * Film d'annonce (brief §8.1) : vignette noire au monogramme, jamais préchargé
 * — c'est la condition pour tenir Lighthouse ≥ 95 et un premier affichage
 * sous deux secondes en 4G lente. Tant que le fichier n'est pas fourni
 * (question V0-09), la carte le dit sans rien inventer.
 */
export function Film({
  url,
  poster,
  libelles,
}: {
  readonly url?: string;
  readonly poster?: string;
  readonly libelles: { readonly titre: string; readonly attente: string; readonly lire: string };
}) {
  const [lecture, setLecture] = useState(false);

  return (
    <section aria-labelledby="film-titre" className="flex flex-col gap-4">
      <h2 id="film-titre" className="jl-etiquette">
        {libelles.titre}
      </h2>

      {url === undefined ? (
        <div
          className="flex aspect-video flex-col items-center justify-center gap-5 border"
          style={{ borderColor: "var(--filet)", background: "#080808" }}
        >
          <Monogram hauteur={48} variante="contour" />
          <p className="jl-doux max-w-xs px-6 text-center text-sm">{libelles.attente}</p>
        </div>
      ) : lecture ? (
        <video
          className="aspect-video w-full"
          controls
          autoPlay
          playsInline
          preload="none"
          {...(poster === undefined ? {} : { poster })}
        >
          <source src={url} type="video/mp4" />
        </video>
      ) : (
        <button
          type="button"
          onClick={() => setLecture(true)}
          className="jl-cible relative flex aspect-video w-full flex-col items-center justify-center gap-5 border"
          style={{ borderColor: "var(--filet)", background: "#080808" }}
        >
          <Monogram hauteur={48} variante="plein" />
          <span className="jl-etiquette">{libelles.lire}</span>
        </button>
      )}
    </section>
  );
}
