"use client";

import { useState } from "react";
import { MOMENTS, MOUVEMENT } from "@/lib/tokens";
import { Filet } from "./Filet";

/** Démonstration des seules animations autorisées (brief §3). */
export function DemoMouvement({ libelle, note }: { readonly libelle: string; readonly note: string }) {
  const [cle, setCle] = useState(0);
  return (
    <div className="flex flex-col gap-5">
      <div key={cle} className="flex flex-col gap-3">
        {MOMENTS.map((moment, index) => (
          <div
            key={moment.id}
            className="jl-apparition"
            style={{ animationDelay: `${index * 120}ms` }}
          >
            <Filet couleur={moment.hex} anime largeur={`${40 + index * 15}%`} />
          </div>
        ))}
      </div>
      <p className="jl-doux max-w-prose text-sm">{note}</p>
      <button
        type="button"
        onClick={() => setCle((n) => n + 1)}
        className="jl-cible self-start border px-4 py-2"
        style={{ borderColor: "var(--filet)" }}
      >
        {libelle}
      </button>
      <p className="jl-doux text-sm">
        {MOUVEMENT.ease} · {MOUVEMENT.court}–{MOUVEMENT.long} ms · glissement ≤{" "}
        {MOUVEMENT.glissementMaxPx} px
      </p>
    </div>
  );
}
