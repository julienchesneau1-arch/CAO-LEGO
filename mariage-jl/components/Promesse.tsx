"use client";

import { useState } from "react";
import { Monogram } from "./Monogram";
import { importerClePublique, sceller } from "@/lib/promesse-crypto";

type Libelles = {
  readonly champ: string;
  readonly sceller: string;
  readonly scelle: string;
  readonly erreur: string;
  readonly indisponible: string;
};

/**
 * Écriture d'un vœu (brief §8.10). Le texte est chiffré **ici**, dans le
 * navigateur : le serveur ne reçoit qu'une enveloppe close.
 *
 * Aucun compteur de participation, aucune comparaison entre invités (§17).
 */
export function Promesse({
  clePublique,
  libelles,
}: {
  readonly clePublique: string | null;
  readonly libelles: Libelles;
}) {
  const [etat, setEtat] = useState<"ecriture" | "envoi" | "scelle" | "erreur">("ecriture");
  const [texte, setTexte] = useState("");

  if (clePublique === null) {
    return <p className="jl-doux">{libelles.indisponible}</p>;
  }

  if (etat === "scelle") {
    return (
      <div className="flex flex-col items-center gap-6">
        {/* L'enveloppe fermée : le sceau au monogramme, et plus rien à lire. */}
        <div
          className="jl-apparition flex aspect-[3/2] w-full max-w-sm items-center justify-center border"
          style={{ borderColor: "var(--filet)", background: "var(--fond)" }}
        >
          <Monogram hauteur={56} variante="plein" titre="Julien & Lauriane" />
        </div>
        <p aria-live="polite" className="jl-titre text-xl">
          {libelles.scelle}
        </p>
      </div>
    );
  }

  const envoyer = async () => {
    if (texte.trim().length < 2) return;
    setEtat("envoi");
    try {
      const enveloppe = await sceller(texte.trim(), await importerClePublique(clePublique));
      const reponse = await fetch("/promesse/sceller", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(enveloppe),
      });
      if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
      setTexte("");
      setEtat("scelle");
    } catch {
      setEtat("erreur");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <label className="flex flex-col gap-2">
        <span className="jl-etiquette">{libelles.champ}</span>
        <textarea
          value={texte}
          onChange={(evenement) => setTexte(evenement.target.value)}
          rows={7}
          maxLength={2000}
          className="border bg-transparent px-4 py-3"
          style={{ borderColor: "var(--filet)", color: "var(--texte)" }}
        />
      </label>

      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={{ borderColor: "var(--filet)" }}>
          {libelles.erreur}
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => void envoyer()}
        disabled={etat === "envoi" || texte.trim().length < 2}
        className="jl-cible self-start border px-6 py-3 disabled:opacity-40"
        style={{ borderColor: "var(--filet)" }}
      >
        {libelles.sceller}
      </button>
    </div>
  );
}
