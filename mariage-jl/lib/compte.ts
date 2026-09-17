/** Décompte partagé entre le serveur (valeur initiale) et le client (le tic). */
export type Restant = {
  readonly jours: number;
  readonly heures: number;
  readonly minutes: number;
  readonly secondes: number;
};

export function restant(cible: number, maintenant: number): Restant {
  const delta = Math.max(0, Math.floor((cible - maintenant) / 1000));
  return {
    jours: Math.floor(delta / 86_400),
    heures: Math.floor((delta % 86_400) / 3_600),
    minutes: Math.floor((delta % 3_600) / 60),
    secondes: delta % 60,
  };
}
