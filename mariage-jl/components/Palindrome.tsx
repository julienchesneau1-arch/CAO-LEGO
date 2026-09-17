"use client";

import { useState } from "react";
import { LIGNES } from "@/lib/palindrome";

/**
 * Le palindrome (brief §8.8) : les lignes s'allument une par une, comme dans
 * le film. « Sauf que… » les rallume en sens inverse. Aucune explication —
 * c'est le propre du texte.
 *
 * Mouvement réduit : les lignes apparaissent d'un coup, sans cascade.
 */
export function Palindrome({
  pivot,
  revoir,
  libelleListe,
  sensEndroit,
  sensInverse,
}: {
  readonly pivot: string;
  readonly revoir: string;
  readonly libelleListe: string;
  readonly sensEndroit: string;
  readonly sensInverse: string;
}) {
  const [inverse, setInverse] = useState(false);
  const ordre = inverse ? [...LIGNES].reverse() : LIGNES;

  return (
    <div className="flex flex-col gap-10">
      {/* Le nom de la liste reste stable ; c'est la région vivante ci-dessous
          qui annonce le changement de sens aux lecteurs d'écran. */}
      <p aria-live="polite" className="sr-only">
        {inverse ? sensInverse : sensEndroit}
      </p>

      <ol
        key={inverse ? "inverse" : "endroit"}
        className="flex flex-col gap-4"
        aria-label={libelleListe}
      >
        {ordre.map((ligne, rang) => (
          <li
            key={`${ligne}-${rang}`}
            className="jl-apparition jl-titre text-xl leading-snug"
            style={{ animationDelay: `${rang * 150}ms` }}
          >
            {ligne}
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={() => setInverse((valeur) => !valeur)}
        aria-pressed={inverse}
        className="jl-cible jl-titre self-start border px-6 py-3 text-xl"
        style={{ borderColor: "var(--filet)" }}
      >
        {pivot}
      </button>

      <a
        href="/"
        className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
      >
        {revoir}
      </a>
    </div>
  );
}
