/**
 * Génération de fichiers `.ics` (brief §8.3 : « Ajouter à mon agenda »).
 * Écrit à la main, sans dépendance : le format est simple, et une
 * bibliothèque de plus serait une dette pour un fichier texte.
 *
 * Règles respectées : lignes en CRLF, pliage à 75 octets, échappement des
 * virgules, points-virgules et retours à la ligne, identifiants stables pour
 * qu'un second téléchargement mette à jour l'événement au lieu de le doubler.
 */
export type EvenementIcs = {
  readonly uid: string;
  readonly titre: string;
  readonly debut: Date;
  readonly fin: Date | null;
  readonly journeeEntiere?: boolean;
  readonly lieu?: string;
  readonly description?: string;
};

const CRLF = "\r\n";

function echapper(valeur: string): string {
  return valeur
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

/** Pliage à 75 octets, la suite préfixée d'une espace (RFC 5545 §3.1). */
function plier(ligne: string): string {
  const octets = Buffer.from(ligne, "utf8");
  if (octets.length <= 75) return ligne;

  const morceaux: string[] = [];
  let debut = 0;
  let limite = 75;
  while (debut < octets.length) {
    let fin = Math.min(debut + limite, octets.length);
    // Ne jamais couper au milieu d'un caractère multi-octets.
    while (fin > debut && fin < octets.length && (octets[fin]! & 0b1100_0000) === 0b1000_0000) {
      fin -= 1;
    }
    morceaux.push(octets.subarray(debut, fin).toString("utf8"));
    debut = fin;
    limite = 74; // les lignes suivantes perdent un octet pour l'espace
  }
  return morceaux.join(`${CRLF} `);
}

const horodatageUtc = (date: Date): string =>
  `${date.toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`;

const jourSeul = (date: Date): string =>
  new Intl.DateTimeFormat("fr-CA", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(date)
    .replace(/-/g, "");

export function construireIcs(
  evenements: ReadonlyArray<EvenementIcs>,
  options: { readonly domaine: string; readonly maintenant?: Date },
): string {
  const maintenant = options.maintenant ?? new Date();
  const lignes: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:-//${options.domaine}//Mariage J&L//FR`,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];

  for (const evenement of evenements) {
    lignes.push("BEGIN:VEVENT");
    lignes.push(`UID:${evenement.uid}`);
    lignes.push(`DTSTAMP:${horodatageUtc(maintenant)}`);
    if (evenement.journeeEntiere === true) {
      const lendemain = new Date(evenement.debut.getTime() + 86_400_000);
      lignes.push(`DTSTART;VALUE=DATE:${jourSeul(evenement.debut)}`);
      lignes.push(`DTEND;VALUE=DATE:${jourSeul(evenement.fin ?? lendemain)}`);
    } else {
      lignes.push(`DTSTART:${horodatageUtc(evenement.debut)}`);
      if (evenement.fin !== null) lignes.push(`DTEND:${horodatageUtc(evenement.fin)}`);
    }
    lignes.push(`SUMMARY:${echapper(evenement.titre)}`);
    if (evenement.lieu !== undefined) lignes.push(`LOCATION:${echapper(evenement.lieu)}`);
    if (evenement.description !== undefined) {
      lignes.push(`DESCRIPTION:${echapper(evenement.description)}`);
    }
    lignes.push("END:VEVENT");
  }

  lignes.push("END:VCALENDAR");
  return `${lignes.map(plier).join(CRLF)}${CRLF}`;
}
