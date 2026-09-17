"use client";

import { useState } from "react";

/**
 * Le lien est toujours lisible en clair : le bouton ne fait que rendre service.
 * Si le presse-papiers est refusé par le navigateur, rien n'est perdu.
 */
export function LienCopiable({
  lien,
  libelleCopier,
  libelleCopie,
}: {
  readonly lien: string;
  readonly libelleCopier: string;
  readonly libelleCopie: string;
}) {
  const [copie, setCopie] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <code
        className="border p-4 text-sm break-all"
        style={{ borderColor: "var(--filet)", fontFamily: "ui-monospace, monospace" }}
      >
        {lien}
      </code>
      <button
        type="button"
        onClick={() => {
          navigator.clipboard?.writeText(lien).then(
            () => setCopie(true),
            () => setCopie(false),
          );
        }}
        className="jl-cible self-start border px-5 py-3"
        style={{ borderColor: "var(--filet)" }}
      >
        {copie ? libelleCopie : libelleCopier}
      </button>
      <p aria-live="polite" className="jl-doux text-sm">
        {copie ? libelleCopie : ""}
      </p>
    </div>
  );
}
