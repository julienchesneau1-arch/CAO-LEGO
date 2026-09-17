/**
 * Boutons d'itinéraire (brief §8.4). Construits depuis le seul élément connu
 * avec certitude : le nom et la commune du domaine (brief §2). Dès que
 * l'adresse complète et les coordonnées seront données (question V1-07), la
 * même fonction les utilisera sans changer les écrans.
 */
export type Itineraire = { readonly cle: string; readonly url: string };

export function itineraires(destination: string): ReadonlyArray<Itineraire> {
  const q = encodeURIComponent(destination);
  return [
    { cle: "apple", url: `https://maps.apple.com/?q=${q}` },
    { cle: "google", url: `https://www.google.com/maps/search/?api=1&query=${q}` },
    { cle: "waze", url: `https://waze.com/ul?q=${q}&navigate=yes` },
  ];
}
