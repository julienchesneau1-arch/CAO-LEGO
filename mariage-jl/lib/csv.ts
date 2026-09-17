/**
 * Lecture du CSV d'import des invités (brief §14).
 * Format attendu, séparateur point-virgule (le format des tableurs français) :
 *
 *     foyer;invites;langue
 *     Famille Exemple;Prénom A|Prénom B;fr
 *
 * Aucune dépendance : un séparateur, des guillemets, c'est tout ce qu'il faut.
 */
export type LigneFoyer = {
  readonly foyer: string;
  readonly invites: ReadonlyArray<string>;
  readonly langue: "fr" | "en";
};

export type ResultatCsv = {
  readonly foyers: ReadonlyArray<LigneFoyer>;
  readonly erreurs: ReadonlyArray<string>;
};

function decouper(ligne: string): string[] {
  const champs: string[] = [];
  let courant = "";
  let entreGuillemets = false;
  for (let i = 0; i < ligne.length; i += 1) {
    const caractere = ligne[i];
    if (caractere === '"') {
      if (entreGuillemets && ligne[i + 1] === '"') {
        courant += '"';
        i += 1;
      } else {
        entreGuillemets = !entreGuillemets;
      }
    } else if (caractere === ";" && !entreGuillemets) {
      champs.push(courant);
      courant = "";
    } else {
      courant += caractere;
    }
  }
  champs.push(courant);
  return champs.map((champ) => champ.trim());
}

export function lireCsvFoyers(contenu: string): ResultatCsv {
  const foyers: LigneFoyer[] = [];
  const erreurs: string[] = [];
  const lignes = contenu
    .replace(/^﻿/, "") // marque d'ordre des octets d'Excel
    .split(/\r?\n/)
    .map((ligne) => ligne.trim())
    .filter((ligne) => ligne !== "");

  for (const [index, ligne] of lignes.entries()) {
    const champs = decouper(ligne);
    const [foyer, invites, langue] = champs;

    // En-tête toléré, quelle que soit sa casse.
    if (index === 0 && foyer?.toLowerCase() === "foyer") continue;

    if (foyer === undefined || foyer === "") {
      erreurs.push(`Ligne ${index + 1} : nom du foyer manquant.`);
      continue;
    }
    const prenoms = (invites ?? "")
      .split("|")
      .map((prenom) => prenom.trim())
      .filter((prenom) => prenom !== "");
    if (prenoms.length === 0) {
      erreurs.push(`Ligne ${index + 1} : aucun invité pour « ${foyer} ».`);
      continue;
    }
    if (langue !== undefined && langue !== "" && langue !== "fr" && langue !== "en") {
      erreurs.push(`Ligne ${index + 1} : langue « ${langue} » inconnue (fr ou en).`);
      continue;
    }
    foyers.push({ foyer, invites: prenoms, langue: langue === "en" ? "en" : "fr" });
  }

  return { foyers, erreurs };
}
