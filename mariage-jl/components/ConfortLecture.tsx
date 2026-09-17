"use client";

import { useEffect, useState } from "react";
import { COOKIE_LANGUE, type Langue } from "@/lib/i18n";
import { TAILLES_TEXTE, type TailleTexte } from "@/lib/tokens";

const CLE = "jl_confort";

type Etat = {
  taille: TailleTexte;
  papier: "oui" | "non";
  mouvement: "normal" | "reduit";
};

const DEFAUT: Etat = { taille: "normale", papier: "non", mouvement: "normal" };

type Libelles = {
  readonly titre: string;
  readonly taille: string;
  readonly tailles: Readonly<Record<TailleTexte, string>>;
  readonly papier: string;
  readonly mouvement: string;
  readonly langue: string;
  readonly bascule: string;
};

/**
 * Noyau du « Confort de lecture » (brief §6, écran 2 du premier lancement).
 * Chaque réglage agit sur un attribut de <html> : aucun composant ne dépend
 * de la taille choisie, et la préférence survit à la fermeture de l'app.
 */
export function ConfortLecture({
  libelles,
  langueCourante,
}: {
  readonly libelles: Libelles;
  readonly langueCourante: Langue;
}) {
  const [etat, setEtat] = useState<Etat>(DEFAUT);

  useEffect(() => {
    try {
      const brut = localStorage.getItem(CLE);
      if (brut !== null) setEtat({ ...DEFAUT, ...(JSON.parse(brut) as Partial<Etat>) });
    } catch {
      /* stockage indisponible : les valeurs par défaut suffisent */
    }
  }, []);

  useEffect(() => {
    const racine = document.documentElement;
    racine.dataset["taille"] = etat.taille;
    racine.dataset["papier"] = etat.papier;
    racine.dataset["mouvement"] = etat.mouvement;
    try {
      localStorage.setItem(CLE, JSON.stringify(etat));
    } catch {
      /* mode privé : on n'insiste pas */
    }
  }, [etat]);

  const basculerLangue = () => {
    const suivante: Langue = langueCourante === "fr" ? "en" : "fr";
    document.cookie = `${COOKIE_LANGUE}=${suivante};path=/;max-age=31536000;samesite=lax`;
    location.reload();
  };

  return (
    <section aria-labelledby="confort-titre" className="flex flex-col gap-5">
      <h2 id="confort-titre" className="jl-etiquette">
        {libelles.titre}
      </h2>

      <fieldset className="flex flex-col gap-3">
        <legend className="jl-doux mb-2">{libelles.taille}</legend>
        <div className="flex flex-wrap gap-3">
          {(Object.keys(TAILLES_TEXTE) as TailleTexte[]).map((taille) => (
            <button
              key={taille}
              type="button"
              aria-pressed={etat.taille === taille}
              onClick={() => setEtat((p) => ({ ...p, taille }))}
              className="jl-cible border px-4 py-2"
              style={{
                borderColor: "var(--filet)",
                background: etat.taille === taille ? "var(--filet)" : "transparent",
              }}
            >
              {libelles.tailles[taille]}
              <span className="jl-doux ml-2">{TAILLES_TEXTE[taille]} px</span>
            </button>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          aria-pressed={etat.papier === "oui"}
          onClick={() => setEtat((p) => ({ ...p, papier: p.papier === "oui" ? "non" : "oui" }))}
          className="jl-cible border px-4 py-2"
          style={{
            borderColor: "var(--filet)",
            background: etat.papier === "oui" ? "var(--filet)" : "transparent",
          }}
        >
          {libelles.papier}
        </button>
        <button
          type="button"
          aria-pressed={etat.mouvement === "reduit"}
          onClick={() =>
            setEtat((p) => ({ ...p, mouvement: p.mouvement === "reduit" ? "normal" : "reduit" }))
          }
          className="jl-cible border px-4 py-2"
          style={{
            borderColor: "var(--filet)",
            background: etat.mouvement === "reduit" ? "var(--filet)" : "transparent",
          }}
        >
          {libelles.mouvement}
        </button>
        <button
          type="button"
          onClick={basculerLangue}
          className="jl-cible border px-4 py-2"
          style={{ borderColor: "var(--filet)" }}
        >
          {libelles.langue} · {libelles.bascule}
        </button>
      </div>
    </section>
  );
}
