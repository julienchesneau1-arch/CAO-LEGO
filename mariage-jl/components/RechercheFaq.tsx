"use client";

import { useMemo, useState } from "react";
import { normaliser } from "@/lib/texte";

type Question = { readonly id: string; readonly question: string; readonly reponse: string };

/**
 * FAQ avec recherche (brief §8.4). Le filtrage se fait dans le téléphone :
 * une fois la page ouverte, la recherche fonctionne sans réseau. Les accents
 * et la casse sont ignorés — personne ne doit taper « accessibilité » juste.
 */
export function RechercheFaq({
  questions,
  libelles,
}: {
  readonly questions: ReadonlyArray<Question>;
  readonly libelles: {
    readonly recherche: string;
    readonly aucun: string;
    readonly reponseAttendue: string;
  };
}) {
  const [terme, setTerme] = useState("");

  const resultats = useMemo(() => {
    const cible = normaliser(terme);
    if (cible === "") return questions;
    return questions.filter((q) =>
      `${normaliser(q.question)} ${normaliser(q.reponse)}`.includes(cible),
    );
  }, [questions, terme]);

  const attendue = (reponse: string): boolean =>
    reponse.includes("[À COMPLÉTER]") || reponse.includes("[TO BE COMPLETED]");

  return (
    <div className="flex flex-col gap-8">
      <label className="flex flex-col gap-2">
        <span className="jl-etiquette">{libelles.recherche}</span>
        <input
          type="search"
          value={terme}
          onChange={(evenement) => setTerme(evenement.target.value)}
          className="jl-cible border bg-transparent px-4 py-3"
          style={{ borderColor: "var(--filet)", color: "var(--texte)" }}
        />
      </label>

      <p aria-live="polite" className="sr-only">
        {resultats.length}
      </p>

      {resultats.length === 0 ? (
        <p className="jl-doux">{libelles.aucun}</p>
      ) : (
        <ul className="flex flex-col gap-8">
          {resultats.map((question) => (
            <li key={question.id} className="flex flex-col gap-3">
              <hr className="jl-filet" />
              <h2 className="jl-titre text-xl">{question.question}</h2>
              <p className={attendue(question.reponse) ? "jl-doux" : "whitespace-pre-line"}>
                {attendue(question.reponse) ? libelles.reponseAttendue : question.reponse}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
