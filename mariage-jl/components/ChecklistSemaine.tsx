"use client";

import { useEffect, useState } from "react";

const CLE = "jl_checklist";

export type Etape = { readonly cle: string; readonly libelle: string };

/**
 * Checklist de la semaine J (brief §8.5). Volontairement **locale au
 * téléphone** : savoir si un invité a préparé sa tenue n'intéresse personne
 * d'autre que lui, et l'envoyer au serveur serait une donnée personnelle
 * collectée sans raison (§11). L'écran le dit en clair.
 */
export function ChecklistSemaine({
  etapes,
  libelles,
}: {
  readonly etapes: ReadonlyArray<Etape>;
  readonly libelles: { readonly titre: string; readonly faite: string; readonly locale: string };
}) {
  const [cochees, setCochees] = useState<ReadonlyArray<string>>([]);
  const [chargee, setChargee] = useState(false);

  useEffect(() => {
    try {
      const brut = localStorage.getItem(CLE);
      if (brut !== null) {
        const lu: unknown = JSON.parse(brut);
        if (Array.isArray(lu)) setCochees(lu.filter((v): v is string => typeof v === "string"));
      }
    } catch {
      // Navigation privée, stockage bloqué : la liste s'affiche vide, sans erreur.
    }
    setChargee(true);
  }, []);

  const basculer = (cle: string): void => {
    const suite = cochees.includes(cle) ? cochees.filter((c) => c !== cle) : [...cochees, cle];
    setCochees(suite);
    try {
      localStorage.setItem(CLE, JSON.stringify(suite));
    } catch {
      // Rien à faire : la case reste cochée à l'écran, simplement pas gardée.
    }
  };

  const faites = etapes.filter((etape) => cochees.includes(etape.cle)).length;

  return (
    <section aria-labelledby="checklist" className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="checklist" className="jl-etiquette">
          {libelles.titre}
        </h2>
        <p className="jl-doux text-sm tabular-nums" aria-live="polite">
          {chargee
            ? libelles.faite
                .replace("{faites}", String(faites))
                .replace("{total}", String(etapes.length))
            : ""}
        </p>
      </div>
      <ul className="flex flex-col">
        {etapes.map((etape) => (
          <li key={etape.cle}>
            <label className="jl-cible flex items-center gap-4 py-2">
              <input
                type="checkbox"
                checked={cochees.includes(etape.cle)}
                onChange={() => basculer(etape.cle)}
              />
              <span
                style={
                  cochees.includes(etape.cle)
                    ? { color: "var(--doux)", textDecoration: "line-through" }
                    : undefined
                }
              >
                {etape.libelle}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="jl-doux text-sm">{libelles.locale}</p>
    </section>
  );
}
