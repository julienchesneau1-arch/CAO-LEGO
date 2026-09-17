"use client";

import { useEffect, useState } from "react";
import { restant, type Restant } from "@/lib/compte";

type Libelles = {
  readonly titre: string;
  readonly jours: string;
  readonly heures: string;
  readonly minutes: string;
  readonly secondes: string;
};

/**
 * Compte à rebours en Bodoni Moda, chiffres tabulaires (brief §8.1).
 * La valeur initiale vient du serveur : aucun décalage au premier affichage,
 * et l'écran reste juste même si le téléphone est mal réglé.
 */
export function CompteARebours({
  cibleIso,
  initial,
  libelles,
}: {
  readonly cibleIso: string;
  readonly initial: Restant;
  readonly libelles: Libelles;
}) {
  const [valeur, setValeur] = useState<Restant>(initial);

  useEffect(() => {
    const cible = new Date(cibleIso).getTime();
    const tic = () => setValeur(restant(cible, Date.now()));
    tic();
    const minuterie = setInterval(tic, 1000);
    return () => clearInterval(minuterie);
  }, [cibleIso]);

  const blocs = [
    { valeur: valeur.jours, libelle: libelles.jours },
    { valeur: valeur.heures, libelle: libelles.heures },
    { valeur: valeur.minutes, libelle: libelles.minutes },
    { valeur: valeur.secondes, libelle: libelles.secondes },
  ];

  return (
    <section aria-labelledby="compte-titre" className="flex flex-col gap-4">
      <h2 id="compte-titre" className="jl-etiquette">
        {libelles.titre}
      </h2>
      <dl className="flex flex-wrap gap-x-8 gap-y-4">
        {blocs.map((bloc) => (
          <div key={bloc.libelle} className="flex flex-col">
            <dd className="jl-titre text-4xl tabular-nums leading-none">
              {String(bloc.valeur).padStart(2, "0")}
            </dd>
            <dt className="jl-doux mt-2 text-sm">{bloc.libelle}</dt>
          </div>
        ))}
      </dl>
    </section>
  );
}
