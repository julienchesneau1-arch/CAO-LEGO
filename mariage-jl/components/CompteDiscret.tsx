"use client";

import { useEffect, useState } from "react";

/**
 * Compte à rebours **discret** vers le moment suivant (brief §8.6). Rien ne
 * clignote, rien ne s'affole : la valeur vient du serveur et se rafraîchit
 * toutes les trente secondes, ce qui suffit pour des minutes.
 */
export function CompteDiscret({
  cibleIso,
  initialMinutes,
  libelles,
}: {
  readonly cibleIso: string;
  readonly initialMinutes: number;
  readonly libelles: {
    readonly dans_minutes: string;
    readonly dans_longtemps: string;
    readonly commence: string;
  };
}) {
  const [minutes, setMinutes] = useState(initialMinutes);

  useEffect(() => {
    const cible = new Date(cibleIso).getTime();
    const tic = () => {
      const ecart = cible - Date.now();
      setMinutes(ecart <= 0 ? 0 : Math.floor(ecart / 60_000));
    };
    tic();
    const minuterie = setInterval(tic, 30_000);
    return () => clearInterval(minuterie);
  }, [cibleIso]);

  if (minutes <= 0) return <span className="jl-doux">{libelles.commence}</span>;

  const texte =
    minutes < 60
      ? libelles.dans_minutes.replace("{minutes}", String(minutes))
      : libelles.dans_longtemps
          .replace("{heures}", String(Math.floor(minutes / 60)))
          .replace("{minutes}", String(minutes % 60));

  return (
    <span className="jl-doux tabular-nums" aria-live="off">
      {texte}
    </span>
  );
}
